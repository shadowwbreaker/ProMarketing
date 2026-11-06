"""Payments through the provider adapter (roadmap Phase 7, D-005, D-008, D-014).

Money is held and moved only by the provider. This module keeps state and a journal; it never
pretends to hold funds. Every outgoing operation stores its idempotency key BEFORE calling the provider.
"""
from __future__ import annotations

import logging
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from audit.services import record
from common.exceptions import DomainError
from common.money import platform_fee
from notifications.services import notify
from orders.events import append_event
from orders.models import Order, OrderItem
from orders.models import OrderStatus as S

from .models import FinancialLedgerEntry, Payment, PaymentAllocation, PaymentWebhookEvent, Payout, RefundRequest
from .providers.base import ProviderCallError, WebhookSignatureError
from .providers.registry import get_payment_provider

logger = logging.getLogger(__name__)
L = FinancialLedgerEntry.Kind


def _ledger(kind, amount, *, item=None, ref="", **meta):
    p = get_payment_provider()
    FinancialLedgerEntry.objects.create(order_item=item, kind=kind, amount_minor=amount, provider=p.code, provider_ref=ref,
                                        meta={k: str(v) for k, v in meta.items()})


# --- payment ---------------------------------------------------------------------------
def start_payment(order_id, *, actor, return_url: str) -> Payment:
    provider = get_payment_provider()
    ok, missing = provider.capabilities.supports_d014()
    if not ok:
        raise DomainError("Платёжный провайдер не поддерживает безопасную модель расчётов", code="provider_unsupported",
                          status_code=503, details={"missing": missing})
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.buyer_id != actor.pk:
            raise DomainError("Нет доступа", code="forbidden", status_code=404)
        if order.status != S.AWAITING_PAYMENT or order.paid_at:
            raise DomainError("Заказ не ожидает оплаты", code="not_awaiting_payment")
        existing = order.payments.filter(status__in=[Payment.Status.CREATED, Payment.Status.PENDING]).first()
        if existing and existing.amount_minor == order.total_minor and existing.confirmation_url:
            return existing  # repeated click → same payment session
        payment = Payment.objects.create(order=order, provider=provider.code, amount_minor=order.total_minor,
                                         idempotency_key=f"pay-{uuid.uuid4().hex}")
    session = provider.create_payment(order_id=str(order.pk), amount_minor=payment.amount_minor, currency=payment.currency,
                                      idempotency_key=payment.idempotency_key, return_url=return_url,
                                      description=f"Заказ {order.pk}")
    Payment.objects.filter(pk=payment.pk).update(provider_payment_id=session.provider_payment_id,
                                                 confirmation_url=session.confirmation_url, status=Payment.Status.PENDING)
    payment.refresh_from_db()
    with transaction.atomic():
        append_event(Order.objects.select_for_update().get(pk=order_id), "payment.started", actor=actor, payment=payment.pk)
    return payment


def handle_webhook(provider_code: str, headers: dict, raw_body: bytes) -> str:
    """Verify signature, deduplicate, reconcile with the provider, apply. Returns outcome string."""
    provider = get_payment_provider()
    if provider.code != provider_code:
        raise DomainError("Неизвестный провайдер", code="unknown_provider", status_code=404)
    try:
        event = provider.verify_webhook(headers, raw_body)
    except WebhookSignatureError as e:
        # Invalid events are NOT stored under their claimed id (an attacker must not be able to block a real event).
        logger.warning("webhook signature invalid provider=%s", provider_code)
        raise DomainError("Неверная подпись", code="invalid_signature", status_code=400) from e
    try:
        with transaction.atomic():
            ev = PaymentWebhookEvent.objects.create(provider=provider_code, provider_event_id=event.event_id, type=event.type,
                                                    raw_body=raw_body.decode(errors="replace"), signature_valid=True)
    except IntegrityError:
        return "duplicate"
    try:
        outcome = _apply_event(provider, event)
        ev.processed_at = timezone.now()
        ev.save(update_fields=["processed_at", "updated_at"])
        return outcome
    except Exception as e:  # keep the event for manual reprocessing
        ev.processing_error = repr(e)[:2000]
        ev.save(update_fields=["processing_error", "updated_at"])
        raise


def _apply_event(provider, event) -> str:
    if event.type.startswith("payment."):
        payment = Payment.objects.filter(provider=provider.code, provider_payment_id=event.object_id).first()
        if not payment:
            return "unknown_payment"
        actual = provider.get_payment_status(event.object_id)  # reconcile: never trust the webhook body alone
        if actual == "succeeded":
            return mark_payment_succeeded(payment.pk)
        if actual in ("cancelled", "failed"):
            Payment.objects.filter(pk=payment.pk, status=Payment.Status.PENDING).update(status=actual)
            return actual
        return "pending"
    if event.type.startswith("refund."):
        refund = RefundRequest.objects.filter(provider_refund_id=event.object_id).first()
        if refund:
            _finish_refund(refund.pk, provider.get_refund_status(event.object_id))
        return "refund"
    if event.type.startswith("payout."):
        po = Payout.objects.filter(provider_payout_id=event.object_id).first()
        if po:
            _finish_payout(po.pk, provider.get_payout_status(event.object_id))
        return "payout"
    return "ignored"


def mark_payment_succeeded(payment_id) -> str:
    from orders.services import on_payment_succeeded

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        if payment.status == Payment.Status.SUCCEEDED:
            return "already_processed"
        order = Order.objects.select_for_update().get(pk=payment.order_id)
        if payment.amount_minor != order.total_minor:
            raise DomainError("Сумма платежа не совпадает с заказом", code="amount_mismatch")
        payment.status = Payment.Status.SUCCEEDED
        payment.succeeded_at = timezone.now()
        payment.save(update_fields=["status", "succeeded_at", "updated_at"])
        for item in order.items.all():
            PaymentAllocation.objects.create(payment=payment, order_item=item, amount_minor=item.price_minor)
            _ledger(L.PAYMENT_SUCCEEDED, item.price_minor, item=item, ref=payment.provider_payment_id or "")
        on_payment_succeeded(order.pk, payment)
    return "paid"


# --- refunds ---------------------------------------------------------------------------
def refunded_amount(item_id, *, include_pending=True) -> int:
    statuses = [RefundRequest.Status.SUCCEEDED]
    if include_pending:
        statuses += [RefundRequest.Status.REQUESTED, RefundRequest.Status.PENDING, RefundRequest.Status.PENDING_RECONCILIATION]
    return RefundRequest.objects.filter(order_item_id=item_id, status__in=statuses).aggregate(s=Sum("amount_minor"))["s"] or 0


def refund_item(item_id, *, amount_minor: int | None, reason: str, actor, decision=None) -> RefundRequest | None:
    """Refund (full when amount is None) one order item through the provider. Double refunds are impossible:
    the item row is locked and the sum of succeeded+pending refunds can never exceed the paid amount."""
    provider = get_payment_provider()
    with transaction.atomic():
        item = OrderItem.objects.select_for_update().get(pk=item_id)
        payment = Payment.objects.filter(order_id=item.order_id, status=Payment.Status.SUCCEEDED).first()
        if not payment:
            return None  # nothing was paid
        payout = Payout.objects.select_for_update().filter(order_item=item).first()
        if payout and payout.status in (Payout.Status.PAID, Payout.Status.REQUESTED, Payout.Status.PENDING_RECONCILIATION):
            raise DomainError("Выплата продавцу уже выполнена — возврат через провайдера невозможен (R-01)",
                              code="payout_already_made", status_code=409)
        already = refunded_amount(item.pk)
        left = item.price_minor - already
        amount = left if amount_minor is None else amount_minor
        if amount <= 0 or amount > left:
            raise DomainError("Сумма возврата превышает оплаченную", code="refund_exceeds_paid", status_code=400,
                              details={"refundable": left})
        if amount < left and not provider.capabilities.partial_refund:
            raise DomainError("Провайдер не поддерживает частичный возврат", code="partial_refund_unsupported", status_code=409)
        refund = RefundRequest.objects.create(order_item=item, payment=payment, amount_minor=amount, reason=reason,
                                              requested_by=actor, dispute_decision=decision,
                                              idempotency_key=f"ref-{uuid.uuid4().hex}")
        _ledger(L.REFUND_REQUESTED, amount, item=item, refund=refund.pk)
        notify(item.order.buyer, "refund.started", "Возврат инициирован", f"{amount / 100:.2f} ₽", order=item.order_id)
        order = Order.objects.select_for_update().get(pk=item.order_id)
        from orders.state import can_transition

        if can_transition(item.status, S.REFUND_PENDING):
            from orders.services import _move

            _move(order, item, S.REFUND_PENDING, actor=actor, event="item.refund_requested", amount=amount)
    try:
        result = provider.request_refund(provider_payment_id=payment.provider_payment_id, amount_minor=amount,
                                         idempotency_key=refund.idempotency_key, reason=reason)
    except ProviderCallError:
        RefundRequest.objects.filter(pk=refund.pk).update(status=RefundRequest.Status.PENDING_RECONCILIATION)
        refund.refresh_from_db()
        return refund
    RefundRequest.objects.filter(pk=refund.pk).update(provider_refund_id=result.provider_id)
    _finish_refund(refund.pk, result.status)
    refund.refresh_from_db()
    return refund


def _finish_refund(refund_id, provider_status: str):
    from orders.services import _move
    from orders.state import can_transition

    with transaction.atomic():
        refund = RefundRequest.objects.select_for_update().get(pk=refund_id)
        if refund.status in (RefundRequest.Status.SUCCEEDED, RefundRequest.Status.FAILED):
            return refund
        item = OrderItem.objects.select_for_update().get(pk=refund.order_item_id)
        order = Order.objects.select_for_update().get(pk=item.order_id)
        if provider_status == "succeeded":
            refund.status = RefundRequest.Status.SUCCEEDED
            refund.save(update_fields=["status", "updated_at"])
            _ledger(L.REFUND_SUCCEEDED, refund.amount_minor, item=item, ref=refund.provider_refund_id or "")
            total = refunded_amount(item.pk, include_pending=False)
            full = total >= item.price_minor
            dst = S.REFUNDED if full else S.PARTIALLY_REFUNDED
            if item.status != dst and can_transition(item.status, dst):
                _move(order, item, dst, event="item.refunded", amount=refund.amount_minor)
            if full:
                from reviews.services import withdraw_for_refunded_item

                withdraw_for_refunded_item(item)
            _adjust_payout_after_refund(item, total)
            notify(order.buyer, "refund.done", "Возврат выполнен", f"{refund.amount_minor / 100:.2f} ₽", order=order.pk)
        elif provider_status == "failed":
            refund.status = RefundRequest.Status.FAILED
            refund.save(update_fields=["status", "updated_at"])
            _ledger(L.REFUND_FAILED, refund.amount_minor, item=item, ref=refund.provider_refund_id or "")
            record(action="refund.failed", subject_type="refund", subject_id=refund.pk, order_id=order.pk)
        else:
            refund.status = RefundRequest.Status.PENDING
            refund.save(update_fields=["status", "updated_at"])
    return refund


def _adjust_payout_after_refund(item: OrderItem, refunded_total: int):
    po = Payout.objects.select_for_update().filter(order_item=item).first()
    if not po or po.status in (Payout.Status.PAID, Payout.Status.CANCELLED):
        return
    remaining = item.price_minor - refunded_total
    if remaining <= 0:
        po.status, po.amount_minor = Payout.Status.CANCELLED, 0
    else:
        po.amount_minor = remaining - platform_fee(remaining, item.order.fee_bps)
    po.save(update_fields=["status", "amount_minor", "updated_at"])


# --- payouts (D-014) ---------------------------------------------------------------------
def create_payout_hold(item: OrderItem) -> Payout:
    refunded = refunded_amount(item.pk, include_pending=False)
    remaining = item.price_minor - refunded
    amount = remaining - platform_fee(remaining, item.order.fee_bps)
    po, created = Payout.objects.get_or_create(order_item=item, defaults={
        "seller_id": item.order.seller_id, "amount_minor": amount, "status": Payout.Status.HOLD,
        "available_at": item.payout_available_at, "idempotency_key": f"po-{uuid.uuid4().hex}"})
    if created:
        _ledger(L.PAYOUT_HOLD, amount, item=item, available_at=item.payout_available_at)
        _ledger(L.PLATFORM_FEE, remaining - amount, item=item)
    return po


def suspend_payout(item: OrderItem, reason: str):
    po = Payout.objects.select_for_update().filter(order_item=item).first()
    if po and po.status in (Payout.Status.HOLD, Payout.Status.AVAILABLE):
        po.status = Payout.Status.SUSPENDED
        po.save(update_fields=["status", "updated_at"])
        _ledger(L.PAYOUT_SUSPENDED, po.amount_minor, item=item, reason=reason)


def resume_payout(item: OrderItem):
    po = Payout.objects.select_for_update().filter(order_item=item).first()
    if po and po.status == Payout.Status.SUSPENDED:
        po.status = Payout.Status.HOLD if po.available_at > timezone.now() else Payout.Status.AVAILABLE
        po.save(update_fields=["status", "updated_at"])
        if po.status == Payout.Status.AVAILABLE:
            _ledger(L.PAYOUT_AVAILABLE, po.amount_minor, item=item)


def release_payouts(now=None) -> int:
    """HOLD → AVAILABLE after 48h if no active dispute on the item (D-014). Internal timer."""
    from support.models import DisputeItem

    now = now or timezone.now()
    n = 0
    for po_id in Payout.objects.filter(status=Payout.Status.HOLD, available_at__lte=now).values_list("pk", flat=True):
        with transaction.atomic():
            po = Payout.objects.select_for_update().get(pk=po_id)
            if po.status != Payout.Status.HOLD:
                continue
            if DisputeItem.objects.filter(order_item_id=po.order_item_id, is_active=True).exists():
                po.status = Payout.Status.SUSPENDED
                po.save(update_fields=["status", "updated_at"])
                continue
            po.status = Payout.Status.AVAILABLE
            po.save(update_fields=["status", "updated_at"])
            _ledger(L.PAYOUT_AVAILABLE, po.amount_minor, item=po.order_item)
            notify(po.seller, "payout.available", "Выплата доступна к выводу", f"{po.amount_minor / 100:.2f} ₽", payout=po.pk)
            n += 1
    return n


def withdraw(payout_id, *, actor) -> Payout:
    provider = get_payment_provider()
    with transaction.atomic():
        po = Payout.objects.select_for_update().select_related("order_item").get(pk=payout_id)
        if po.seller_id != actor.pk:
            raise DomainError("Нет доступа", code="forbidden", status_code=404)
        if po.status != Payout.Status.AVAILABLE:
            raise DomainError("Выплата недоступна к выводу", code="payout_not_available", details={"status": po.status})
        po.status = Payout.Status.REQUESTED
        po.save(update_fields=["status", "updated_at"])
        _ledger(L.PAYOUT_REQUESTED, po.amount_minor, item=po.order_item)
        notify(po.seller, "payout.started", "Выплата инициирована", f"{po.amount_minor / 100:.2f} ₽", payout=po.pk)
    try:
        result = provider.request_payout(seller_ref=str(po.seller_id), amount_minor=po.amount_minor,
                                         idempotency_key=po.idempotency_key, deal_ref=str(po.order_item.order_id))
    except ProviderCallError:
        Payout.objects.filter(pk=po.pk).update(status=Payout.Status.PENDING_RECONCILIATION)
        po.refresh_from_db()
        return po
    Payout.objects.filter(pk=po.pk).update(provider_payout_id=result.provider_id)
    return _finish_payout(po.pk, result.status)


def _finish_payout(payout_id, provider_status: str) -> Payout:
    with transaction.atomic():
        po = Payout.objects.select_for_update().select_related("order_item").get(pk=payout_id)
        if po.status in (Payout.Status.PAID,):
            return po
        if provider_status == "succeeded":
            po.status, po.paid_at = Payout.Status.PAID, timezone.now()
            _ledger(L.PAYOUT_PAID, po.amount_minor, item=po.order_item, ref=po.provider_payout_id or "")
            notify(po.seller, "payout.paid", "Выплата выполнена", f"{po.amount_minor / 100:.2f} ₽", payout=po.pk)
        elif provider_status == "failed":
            po.status = Payout.Status.FAILED
            _ledger(L.PAYOUT_FAILED, po.amount_minor, item=po.order_item, ref=po.provider_payout_id or "")
        po.save(update_fields=["status", "paid_at", "updated_at"])
    return po


def retry_failed_payout(payout_id, *, actor) -> Payout:
    """Failed payout can be retried with a NEW idempotency key (the provider rejected the old one)."""
    with transaction.atomic():
        po = Payout.objects.select_for_update().get(pk=payout_id)
        if po.seller_id != actor.pk:
            raise DomainError("Нет доступа", code="forbidden", status_code=404)
        if po.status != Payout.Status.FAILED:
            raise DomainError("Повтор возможен только для неуспешной выплаты", code="payout_not_failed")
        po.status = Payout.Status.AVAILABLE
        po.idempotency_key = f"po-{uuid.uuid4().hex}"
        po.provider_payout_id = None
        po.save(update_fields=["status", "idempotency_key", "provider_payout_id", "updated_at"])
    return withdraw(payout_id, actor=actor)

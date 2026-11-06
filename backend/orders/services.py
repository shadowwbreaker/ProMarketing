"""Order lifecycle (roadmap Phase 6). All status changes go through `_move` → state machine + event + aggregate."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from catalog.models import AdvertisingOffer
from catalog.public import sellable_accounts, sellable_networks
from chats.models import Chat
from common.exceptions import DomainError
from common.money import platform_fee
from notifications.services import notify

from .events import append_event
from .models import Order, OrderItem, OrderTermsProposal, OrderTermsVersion, PublicationProof
from .models import OrderStatus as S
from .state import aggregate_status, check_transition

TERM_FIELDS = ["brand", "site_url", "brief", "ad_text", "cta", "links", "publish_deadline", "placement_days",
               "extra_requirements", "platform_removal_policy", "materials_deadline"]


def _hash_terms(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _lock(order_id) -> Order:
    return Order.objects.select_for_update().get(pk=order_id)


def refresh_aggregate(order: Order) -> str:
    new = aggregate_status(list(order.items.values_list("status", flat=True)))
    if new != order.status:
        order.status = new
        order.save(update_fields=["status", "updated_at"])
    return new


def _move(order: Order, item: OrderItem, dst: str, *, actor=None, event: str, **payload) -> OrderItem:
    src = item.status
    check_transition(src, dst)
    item.status = dst
    item.save()
    append_event(order, event, actor=actor, item=item, from_status=src, to_status=dst, **payload)
    refresh_aggregate(order)
    return item


def distribute(total: int, weights: list[int]) -> list[int]:
    """Split `total` proportionally to `weights`; parts sum exactly to total (largest remainder)."""
    wsum = sum(weights)
    raw = [total * w / wsum for w in weights]
    parts = [int(x) for x in raw]
    rest = total - sum(parts)
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - parts[i], reverse=True)[:rest]:
        parts[i] += 1
    return parts


# --- creation ---------------------------------------------------------------------
@transaction.atomic
def create_order(*, buyer, terms: dict, offer_id=None, network_id=None, network_item_ids=None) -> Order:
    """Create an order with frozen prices and terms (roadmap 6.1). Ready for payment (AWAITING_PAYMENT)."""
    if not buyer.is_email_verified:
        raise DomainError("Подтвердите email, чтобы оформить заказ", code="email_not_verified", status_code=403)
    lines: list[tuple] = []  # (offer, price)
    network = None
    if offer_id:
        offer = AdvertisingOffer.objects.select_related("social_account").filter(
            pk=offer_id, is_active=True, social_account__in=sellable_accounts()).first()
        if not offer:
            raise DomainError("Предложение недоступно для заказа", code="offer_unavailable", status_code=400)
        lines.append((offer, offer.price_minor))
    elif network_id:
        network = sellable_networks().filter(pk=network_id).first()
        if not network:
            raise DomainError("Сетка недоступна для заказа", code="network_unavailable", status_code=400)
        items = list(network.items.select_related("offer__social_account").order_by("created_at"))
        if network_item_ids:
            if not network.allow_partial_purchase:
                raise DomainError("Продавец не разрешил покупать аккаунты сетки по отдельности", code="partial_not_allowed", status_code=400)
            wanted = {str(i) for i in network_item_ids}
            items = [i for i in items if str(i.pk) in wanted]
            if len(items) != len(wanted) or not items:
                raise DomainError("Выбраны аккаунты не из этой сетки", code="bad_network_items", status_code=400)
            prices = [i.price_minor for i in items]
        else:
            prices = distribute(network.total_price_minor, [i.price_minor for i in items]) if network.total_price_minor \
                else [i.price_minor for i in items]
        lines = [(i.offer, p) for i, p in zip(items, prices, strict=True)]
    else:
        raise DomainError("Укажите предложение или сетку", code="nothing_to_order", status_code=400)

    seller = lines[0][0].social_account.owner
    if seller.pk == buyer.pk:
        raise DomainError("Нельзя заказать рекламу у самого себя", code="self_order", status_code=400)
    fee_bps = settings.PLATFORM_FEE_BPS
    order = Order.objects.create(buyer=buyer, seller=seller, network=network,
                                 fee_bps=fee_bps, total_minor=sum(p for _, p in lines), status=S.DRAFT)
    for offer, price in lines:
        fee = platform_fee(price, fee_bps)  # D-015: fee deducted from the seller's part
        OrderItem.objects.create(order=order, social_account=offer.social_account, offer=offer, price_minor=price,
                                 fee_minor=fee, seller_amount_minor=price - fee, status=S.DRAFT)
    placement = max(o.placement_days for o, _ in lines)
    data = {k: terms.get(k) for k in TERM_FIELDS if terms.get(k) not in (None, "")}
    data.setdefault("placement_days", placement)
    data["ad_format"] = lines[0][0].ad_format
    version = OrderTermsVersion.objects.create(order=order, version=1, proposed_by=buyer, agreed_by_buyer_at=timezone.now(),
                                               content_hash=_hash_terms(data), **data)
    order.current_terms_version = version
    order.save(update_fields=["current_terms_version", "updated_at"])
    Chat.objects.create(order=order)
    append_event(order, "order.created", actor=buyer, total=order.total_minor, terms_hash=version.content_hash)
    for item in order.items.all():
        _move(order, item, S.AWAITING_PAYMENT, actor=buyer, event="item.submitted")
    return order


# --- payment hooks (called by payments.services) ------------------------------------
def on_payment_succeeded(order_id, payment) -> Order:
    with transaction.atomic():
        order = _lock(order_id)
        if order.paid_at:
            return order  # idempotent
        now = timezone.now()
        order.paid_at = now
        order.save(update_fields=["paid_at", "updated_at"])
        deadline = now + timedelta(hours=settings.SELLER_ACCEPT_TIMEOUT_HOURS)
        for item in order.items.select_for_update():
            if item.status != S.AWAITING_PAYMENT:
                continue
            _move(order, item, S.PAID, event="item.paid", payment=payment.pk)
            item.accept_deadline = deadline
            _move(order, item, S.AWAITING_SELLER_ACCEPTANCE, event="item.awaiting_acceptance", deadline=deadline.isoformat())
        notify(order.seller, "order.new", "Новый оплаченный заказ", f"Примите заказ до {deadline:%d.%m %H:%M} UTC", order=order.pk)
        notify(order.buyer, "order.paid", "Оплата получена", "Ждём, когда продавец примет заказ", order=order.pk)
    return order


def cancel_unpaid(order_id, *, actor) -> Order:
    with transaction.atomic():
        order = _lock(order_id)
        if actor.pk != order.buyer_id:
            raise DomainError("Нет доступа", code="forbidden", status_code=404)
        if order.paid_at or order.status not in (S.AWAITING_PAYMENT, S.DRAFT):
            raise DomainError("Оплаченный заказ отменяется через возврат", code="already_paid")
        for item in order.items.select_for_update():
            _move(order, item, S.CANCELLED, actor=actor, event="item.cancelled_unpaid")
    return order


# --- seller actions --------------------------------------------------------------------
def _seller_item(order_id, item_id, actor) -> tuple[Order, OrderItem]:
    order = _lock(order_id)
    if order.seller_id != actor.pk:
        raise DomainError("Нет доступа", code="forbidden", status_code=404)
    item = order.items.select_for_update().get(pk=item_id)
    return order, item


def _buyer_item(order_id, item_id, actor) -> tuple[Order, OrderItem]:
    order = _lock(order_id)
    if order.buyer_id != actor.pk:
        raise DomainError("Нет доступа", code="forbidden", status_code=404)
    item = order.items.select_for_update().get(pk=item_id)
    return order, item


def accept_item(order_id, item_id, *, actor) -> OrderItem:
    with transaction.atomic():
        order, item = _seller_item(order_id, item_id, actor)
        if item.status != S.AWAITING_SELLER_ACCEPTANCE:
            check_transition(item.status, S.IN_PROGRESS)
        if item.accept_deadline and item.accept_deadline < timezone.now():
            raise DomainError("Срок принятия заказа истёк", code="accept_deadline_passed")
        now = timezone.now()
        terms = order.current_terms_version
        item.accepted_at = now
        item.publish_deadline = terms.publish_deadline or now + timedelta(days=item.offer.publish_within_days)
        if not order.seller_terms_accepted_at:
            order.seller_terms_accepted_at = now
            order.save(update_fields=["seller_terms_accepted_at", "updated_at"])
            append_event(order, "terms.accepted_by_seller", actor=actor, version=terms.version, terms_hash=terms.content_hash)
        _move(order, item, S.IN_PROGRESS, actor=actor, event="item.accepted", publish_deadline=item.publish_deadline.isoformat())
        notify(order.buyer, "order.accepted", "Продавец принял заказ", f"Публикация до {item.publish_deadline:%d.%m.%Y}", order=order.pk)
    return item


def decline_item(order_id, item_id, *, actor, reason: str) -> OrderItem:
    from payments.services import refund_item

    with transaction.atomic():
        order, item = _seller_item(order_id, item_id, actor)
        _move(order, item, S.CANCELLED, actor=actor, event="item.declined_by_seller", reason=reason)
    refund_item(item.pk, amount_minor=None, reason=f"Продавец отказался: {reason}", actor=actor)
    return item


def mark_awaiting_publication(order_id, item_id, *, actor) -> OrderItem:
    with transaction.atomic():
        order, item = _seller_item(order_id, item_id, actor)
        return _move(order, item, S.AWAITING_PUBLICATION, actor=actor, event="item.ready_for_publication")


def submit_proof(order_id, item_id, *, actor, video_url: str, published_at, notes: str = "", screenshot=None) -> PublicationProof:
    """Seller provides proof (roadmap 6.3) → PUBLISHED → AWAITING_BUYER_CONFIRMATION."""
    with transaction.atomic():
        order, item = _seller_item(order_id, item_id, actor)
        if item.status not in (S.IN_PROGRESS, S.AWAITING_PUBLICATION):
            check_transition(item.status, S.PUBLISHED)
        _validate_video_url(item, video_url)
        if published_at > timezone.now() + timedelta(minutes=5):
            raise DomainError("Дата публикации в будущем", code="bad_published_at", status_code=400)
        proof = PublicationProof.objects.create(order_item=item, video_url=video_url, profile_url=item.social_account.profile_url,
                                                published_at=published_at, notes=notes, submitted_by=actor, screenshot=screenshot)
        item.published_at = published_at
        item.placement_until = published_at + timedelta(days=order.current_terms_version.placement_days)
        _move(order, item, S.PUBLISHED, actor=actor, event="item.published", video_url=video_url)
        item.confirm_deadline = timezone.now() + timedelta(hours=settings.BUYER_CONFIRM_WINDOW_HOURS)
        _move(order, item, S.AWAITING_BUYER_CONFIRMATION, actor=actor, event="item.awaiting_confirmation",
              confirm_deadline=item.confirm_deadline.isoformat())
        notify(order.buyer, "order.published", "Реклама опубликована", "Проверьте публикацию и подтвердите выполнение", order=order.pk)
        transaction.on_commit(lambda: _schedule_check(item.pk, "proof"))
    return proof


def _schedule_check(item_id, trigger):
    from .tasks import check_publication

    check_publication.delay(str(item_id), trigger)


_VIDEO_HOSTS = {"tiktok": ("tiktok.com",), "youtube": ("youtube.com", "youtu.be"), "instagram": ("instagram.com",)}


def _validate_video_url(item: OrderItem, url: str):
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    allowed = _VIDEO_HOSTS[item.social_account.platform]
    if urlparse(url).scheme != "https" or not any(host == h or host.endswith("." + h) for h in allowed):
        raise DomainError("Ссылка должна вести на публикацию на платформе аккаунта", code="bad_video_url", status_code=400)


# --- buyer actions -----------------------------------------------------------------------
def confirm_item(order_id, item_id, *, actor=None, auto: bool = False) -> OrderItem:
    """Buyer confirms (or system auto-confirms after the window). Starts the 48h payout hold (D-014)."""
    from payments.services import create_payout_hold

    with transaction.atomic():
        if auto:
            order = _lock(order_id)
            item = order.items.select_for_update().get(pk=item_id)
        else:
            order, item = _buyer_item(order_id, item_id, actor)
        if item.status != S.AWAITING_BUYER_CONFIRMATION:
            raise DomainError("Подтвердить можно только опубликованный заказ", code="not_awaiting_confirmation")
        item.confirmed_at = timezone.now()
        item.payout_available_at = item.confirmed_at + timedelta(hours=settings.PAYOUT_HOLD_HOURS)
        _move(order, item, S.COMPLETED, actor=actor, event="item.auto_confirmed" if auto else "item.confirmed")
        create_payout_hold(item)
        notify(order.seller, "order.confirmed", "Покупатель подтвердил выполнение",
               f"Выплата станет доступна {item.payout_available_at:%d.%m %H:%M} UTC, если не будет жалоб", order=order.pk)
    return item


def request_rework(order_id, item_id, *, actor, comment: str) -> OrderItem:
    """Buyer asks to fix the publication without opening a dispute."""
    with transaction.atomic():
        order, item = _buyer_item(order_id, item_id, actor)
        _move(order, item, S.IN_PROGRESS, actor=actor, event="item.rework_requested", comment=comment)
        notify(order.seller, "order.rework", "Покупатель просит исправить публикацию", comment, order=order.pk)
    return item


def cancel_before_acceptance(order_id, item_id, *, actor) -> OrderItem:
    """Buyer may cancel a paid item until the seller accepts it — full refund, no dispute needed."""
    from payments.services import refund_item

    with transaction.atomic():
        order, item = _buyer_item(order_id, item_id, actor)
        if item.status != S.AWAITING_SELLER_ACCEPTANCE:
            raise DomainError("После принятия заказа продавцом отмена — через жалобу", code="already_accepted")
        _move(order, item, S.CANCELLED, actor=actor, event="item.cancelled_by_buyer")
    refund_item(item.pk, amount_minor=None, reason="Отмена покупателем до принятия", actor=actor)
    return item


def mark_materials_delivered(order_id, *, actor) -> Order:
    """Scenario 14: if materials came after the agreed deadline, publish deadlines shift by the delay."""
    with transaction.atomic():
        order = _lock(order_id)
        if order.buyer_id != actor.pk:
            raise DomainError("Нет доступа", code="forbidden", status_code=404)
        if order.materials_delivered_at:
            return order
        now = timezone.now()
        order.materials_delivered_at = now
        order.save(update_fields=["materials_delivered_at", "updated_at"])
        md = order.current_terms_version.materials_deadline
        delay = now - md if md and now > md else None
        append_event(order, "materials.delivered", actor=actor, delay_seconds=int(delay.total_seconds()) if delay else 0)
        if delay:
            for item in order.items.select_for_update().filter(status__in=[S.IN_PROGRESS, S.AWAITING_PUBLICATION]):
                if item.publish_deadline:
                    old = item.publish_deadline
                    item.publish_deadline = old + delay
                    item.save(update_fields=["publish_deadline", "updated_at"])
                    append_event(order, "item.deadline_extended", item=item, old=old.isoformat(), new=item.publish_deadline.isoformat(),
                                 reason="materials_delayed")
        notify(order.seller, "order.materials", "Покупатель передал материалы", "", order=order.pk)
    return order


# --- terms changes (scenario 11) ---------------------------------------------------------
EDITABLE_AFTER_PAYMENT = {"brief", "ad_text", "cta", "links", "publish_deadline", "extra_requirements", "site_url"}


def propose_terms(order_id, *, actor, changes: dict, comment: str = "") -> OrderTermsProposal:
    with transaction.atomic():
        order = _lock(order_id)
        if actor.pk not in (order.buyer_id, order.seller_id):
            raise DomainError("Нет доступа", code="forbidden", status_code=404)
        bad = set(changes) - EDITABLE_AFTER_PAYMENT
        if bad or not changes:
            raise DomainError("Эти условия нельзя изменить", code="bad_terms_fields", status_code=400, details={"fields": sorted(bad)})
        order.terms_proposals.filter(status=OrderTermsProposal.Status.PENDING).update(status=OrderTermsProposal.Status.WITHDRAWN)
        p = OrderTermsProposal.objects.create(order=order, proposed_by=actor, changes=changes, comment=comment)
        append_event(order, "terms.proposed", actor=actor, proposal=p.pk, fields=",".join(sorted(changes)))
        other = order.seller if actor.pk == order.buyer_id else order.buyer
        notify(other, "order.terms_proposed", "Предложено изменить условия заказа", comment, order=order.pk)
    return p


def decide_terms(order_id, proposal_id, *, actor, accept: bool) -> OrderTermsProposal:
    with transaction.atomic():
        order = _lock(order_id)
        p = order.terms_proposals.select_for_update().get(pk=proposal_id)
        if p.status != OrderTermsProposal.Status.PENDING:
            raise DomainError("Предложение уже рассмотрено", code="proposal_closed")
        if actor.pk not in (order.buyer_id, order.seller_id) or actor.pk == p.proposed_by_id:
            raise DomainError("Решение принимает другая сторона", code="forbidden", status_code=403)
        p.decided_by, p.decided_at = actor, timezone.now()
        if accept:
            cur = order.current_terms_version
            data = {k: getattr(cur, k) for k in TERM_FIELDS + ["ad_format"]}
            data.update(p.changes)
            now = timezone.now()
            v = OrderTermsVersion.objects.create(order=order, version=cur.version + 1, proposed_by=p.proposed_by,
                                                 agreed_by_buyer_at=now, agreed_by_seller_at=now,
                                                 content_hash=_hash_terms(data), **data)
            order.current_terms_version = v
            order.save(update_fields=["current_terms_version", "updated_at"])
            p.status, p.resulting_version = OrderTermsProposal.Status.ACCEPTED, v
            append_event(order, "terms.changed", actor=actor, version=v.version, terms_hash=v.content_hash)
        else:
            p.status = OrderTermsProposal.Status.REJECTED
            append_event(order, "terms.rejected", actor=actor, proposal=p.pk)
        p.save()
    return p


# --- timers (internal, never touch social platforms except one-off checks D-010) -----------
def expire_unaccepted(now=None) -> int:
    """Seller did not accept in time → EXPIRED + full refund (scenario 1, no work was started)."""
    from payments.services import refund_item

    now = now or timezone.now()
    ids = list(OrderItem.objects.filter(status=S.AWAITING_SELLER_ACCEPTANCE, accept_deadline__lt=now).values_list("pk", flat=True))
    n = 0
    for item_id in ids:
        with transaction.atomic():
            item = OrderItem.objects.select_for_update().get(pk=item_id)
            if item.status != S.AWAITING_SELLER_ACCEPTANCE:
                continue
            order = _lock(item.order_id)
            _move(order, item, S.EXPIRED, event="item.expired_not_accepted")
            notify(order.buyer, "order.expired", "Продавец не принял заказ вовремя", "Деньги возвращаются", order=order.pk)
        refund_item(item_id, amount_minor=None, reason="Продавец не принял заказ в срок", actor=None)
        n += 1
    return n


def process_confirmation_windows(now=None) -> int:
    """Buyer silent after the window → one publication check → auto-confirm if the video is there (scenario 6)."""
    now = now or timezone.now()
    ids = list(OrderItem.objects.filter(status=S.AWAITING_BUYER_CONFIRMATION, confirm_deadline__lt=now).values_list("pk", flat=True))
    for item_id in ids:
        _schedule_check(item_id, "window_end")
    return len(ids)


def notify_missed_publish_deadlines(now=None) -> int:
    """Scenario 2: no automatic refund — the buyer is told they can complain; the seller is reminded."""
    now = now or timezone.now()
    n = 0
    for item in OrderItem.objects.filter(status__in=[S.IN_PROGRESS, S.AWAITING_PUBLICATION], publish_deadline__lt=now).select_related("order"):
        order = item.order
        if order.events.filter(order_item=item, type="item.publish_deadline_missed").exists():
            continue
        with transaction.atomic():
            o = _lock(order.pk)
            append_event(o, "item.publish_deadline_missed", item=item)
        notify(order.buyer, "order.deadline_missed", "Продавец пропустил срок публикации", "Вы можете открыть жалобу", order=order.pk)
        notify(order.seller, "order.deadline_missed", "Срок публикации истёк", "Опубликуйте рекламу или свяжитесь с покупателем", order=order.pk)
        n += 1
    return n


def notify_deadlines_soon(now=None) -> int:
    """Roadmap 8.2: «Приближается дедлайн» — once per item, 24h before publish deadline."""
    now = now or timezone.now()
    n = 0
    qs = OrderItem.objects.filter(status__in=[S.IN_PROGRESS, S.AWAITING_PUBLICATION], publish_deadline__gt=now,
                                  publish_deadline__lte=now + timedelta(hours=24)).select_related("order")
    for item in qs:
        if item.order.events.filter(order_item=item, type="item.deadline_soon").exists():
            continue
        with transaction.atomic():
            append_event(_lock(item.order_id), "item.deadline_soon", item=item)
        notify(item.order.seller, "order.deadline_soon", "До срока публикации меньше суток",
               f"Опубликуйте рекламу до {item.publish_deadline:%d.%m %H:%M} UTC", order=item.order_id)
        n += 1
    return n

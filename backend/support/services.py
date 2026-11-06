"""Support & arbitration (roadmap Phase 9, docs/SUPPORT_AND_DISPUTES.md).

Principles (FunPay-style, adapted): a complaint never refunds automatically; the other side can answer and
provide evidence; staff decide on facts with a mandatory comment; money moves only through the payment
provider; every staff action is in the append-only audit log.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import UserSanction
from audit.services import record
from chats.services import lock_chat
from common.exceptions import DomainError, InvalidTransition
from notifications.services import notify
from orders.events import append_event
from orders.models import Order, OrderItem
from orders.models import OrderStatus as S
from orders.services import _move
from orders.state import can_transition

from .models import (
    ACTIVE_DISPUTE_STATUSES,
    Dispute,
    DisputeAction,
    DisputeDecision,
    DisputeEvidence,
    DisputeItem,
    DisputeMessage,
    DisputeReason,
)
from .models import DisputeStatus as D

APPEAL_DAYS = 7
MIN_DESCRIPTION = 20

DISPUTE_TRANSITIONS = {
    D.OPEN: {D.WAITING_SELLER, D.WAITING_BUYER, D.UNDER_REVIEW},
    D.WAITING_SELLER: {D.UNDER_REVIEW, D.EVIDENCE_REQUESTED, D.ESCALATED, D.WAITING_BUYER, D.RESOLVED, D.REJECTED},
    D.WAITING_BUYER: {D.UNDER_REVIEW, D.EVIDENCE_REQUESTED, D.ESCALATED, D.WAITING_SELLER, D.RESOLVED, D.REJECTED},
    D.UNDER_REVIEW: {D.EVIDENCE_REQUESTED, D.ESCALATED, D.RESOLVED, D.REJECTED, D.WAITING_SELLER, D.WAITING_BUYER},
    D.EVIDENCE_REQUESTED: {D.UNDER_REVIEW, D.ESCALATED, D.RESOLVED, D.REJECTED},
    D.ESCALATED: {D.UNDER_REVIEW, D.EVIDENCE_REQUESTED, D.RESOLVED, D.REJECTED},
    D.APPEALED: {D.UNDER_REVIEW, D.EVIDENCE_REQUESTED, D.RESOLVED, D.REJECTED, D.CLOSED},
    D.RESOLVED: {D.CLOSED, D.APPEALED},
    D.REJECTED: {D.CLOSED, D.APPEALED},
    D.CLOSED: set(),
}

BUYER_DISPUTABLE = {S.AWAITING_SELLER_ACCEPTANCE, S.IN_PROGRESS, S.AWAITING_PUBLICATION, S.PUBLISHED,
                    S.AWAITING_BUYER_CONFIRMATION, S.COMPLETED, S.PARTIALLY_REFUNDED}
SELLER_DISPUTABLE = {S.IN_PROGRESS, S.AWAITING_PUBLICATION, S.PUBLISHED, S.AWAITING_BUYER_CONFIRMATION}

FINANCIAL = {DisputeDecision.Type.FULL_REFUND, DisputeDecision.Type.PARTIAL_REFUND}
FINAL = {DisputeDecision.Type.FULL_REFUND, DisputeDecision.Type.PARTIAL_REFUND, DisputeDecision.Type.REJECT,
         DisputeDecision.Type.REDO, DisputeDecision.Type.EXTEND, DisputeDecision.Type.IN_FAVOR_OF_SELLER}


def _set_status(d: Dispute, dst: str, *, actor=None, comment: str = "", staff: bool = False):
    src = d.status
    if dst == src:
        return
    if dst not in DISPUTE_TRANSITIONS.get(src, set()):
        raise InvalidTransition(f"Переход спора {src} → {dst} недопустим")
    d.status = dst
    d.save(update_fields=["status", "updated_at"])
    record(action="dispute.status", subject_type="dispute", subject_id=d.pk, actor=actor, is_staff_action=staff,
           order_id=d.order_id, before={"status": src}, after={"status": dst}, comment=comment)


def _role(order: Order, user) -> str:
    if user.pk == order.buyer_id:
        return "buyer"
    if user.pk == order.seller_id:
        return "seller"
    raise DomainError("Нет доступа", code="forbidden", status_code=404)


def _attach_evidence(d: Dispute, user, evidence: list[dict]):
    from files.models import Attachment

    for ev in evidence or []:
        att = None
        if ev.get("attachment"):
            att = Attachment.objects.filter(pk=ev["attachment"], owner=user, scan_status="clean").first()
            if not att:
                raise DomainError("Вложение не найдено", code="bad_attachment", status_code=400)
        url = (ev.get("url") or "").strip()
        if not att and not url:
            raise DomainError("Доказательство: нужен файл или ссылка", code="bad_evidence", status_code=400)
        DisputeEvidence.objects.create(dispute=d, submitted_by=user, attachment=att, url=url,
                                       description=(ev.get("description") or "")[:4000], sha256=att.sha256 if att else "")


# --- opening ----------------------------------------------------------------------------
def open_dispute(order_id, *, actor, item_ids: list, reason_code: str, description: str, evidence: list[dict] | None = None) -> Dispute:
    from payments.services import suspend_payout

    description = (description or "").strip()
    if len(description) < MIN_DESCRIPTION:
        raise DomainError(f"Опишите проблему подробнее (не короче {MIN_DESCRIPTION} символов)", code="description_required", status_code=400)
    reason = DisputeReason.objects.filter(code=reason_code, is_active=True).first()
    if not reason:
        raise DomainError("Неизвестная причина", code="bad_reason", status_code=400)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        role = _role(order, actor)
        if reason.allowed_for not in (role, "both"):
            raise DomainError("Эта причина недоступна для вашей роли", code="reason_not_allowed", status_code=400)
        items = list(order.items.select_for_update().filter(pk__in=item_ids)) if item_ids else list(order.items.select_for_update())
        if not items or (item_ids and len(items) != len(set(map(str, item_ids)))):
            raise DomainError("Выберите позиции этого заказа", code="bad_items", status_code=400)

        # Scenario 15: a claim on an item that is already disputed joins that dispute as a counter-claim.
        active = DisputeItem.objects.filter(order_item__in=items, is_active=True).select_related("dispute").first()
        if active:
            d = Dispute.objects.select_for_update().get(pk=active.dispute_id)
            if d.opened_by_id == actor.pk:
                raise DomainError("По этой позиции у вас уже есть открытая жалоба", code="already_disputed")
            d.has_counterclaim = True
            d.save(update_fields=["has_counterclaim", "updated_at"])
            DisputeMessage.objects.create(dispute=d, author=actor, body=f"Встречная претензия ({reason.title}): {description}")
            _attach_evidence(d, actor, evidence)
            append_event(order, "dispute.counterclaim", actor=actor, dispute=d.pk, reason=reason.code)
            if d.status in (D.WAITING_SELLER, D.WAITING_BUYER):
                _set_status(d, D.UNDER_REVIEW, actor=actor, comment="встречная претензия")
            return d

        allowed = BUYER_DISPUTABLE if role == "buyer" else SELLER_DISPUTABLE
        bad = [i for i in items if i.status not in allowed]
        if bad:
            raise DomainError("По этим позициям жалоба сейчас недоступна", code="not_disputable", status_code=400,
                              details={"items": [str(i.pk) for i in bad], "statuses": [i.status for i in bad]})
        now = timezone.now()
        d = Dispute.objects.create(order=order, opened_by=actor, reason=reason, description=description,
                                   response_due_at=now + timedelta(hours=settings.DISPUTE_RESPONSE_HOURS))
        for it in items:
            DisputeItem.objects.create(dispute=d, order_item=it, status_before=it.status)
            _move(order, it, S.DISPUTED, actor=actor, event="item.disputed", dispute=d.pk)
            suspend_payout(it, reason=f"dispute {d.pk}")
        _attach_evidence(d, actor, evidence)
        _set_status(d, D.WAITING_SELLER if role == "buyer" else D.WAITING_BUYER, actor=actor)
        lock_chat(order)
        append_event(order, "dispute.opened", actor=actor, dispute=d.pk, reason=reason.code)
        other = order.seller if role == "buyer" else order.buyer
    notify(other, "dispute.opened", "Открыта жалоба по заказу",
           f"Причина: {reason.title}. Ответьте до {d.response_due_at:%d.%m %H:%M} UTC", order=order.pk, dispute=d.pk)
    return d


# --- parties ------------------------------------------------------------------------------
def party_reply(dispute_id, *, actor, body: str, evidence: list[dict] | None = None) -> Dispute:
    body = (body or "").strip()
    if not body and not evidence:
        raise DomainError("Пустой ответ", code="empty", status_code=400)
    with transaction.atomic():
        d = Dispute.objects.select_for_update().select_related("order").get(pk=dispute_id)
        role = _role(d.order, actor)
        if d.status not in ACTIVE_DISPUTE_STATUSES:
            raise DomainError("Спор закрыт", code="dispute_closed")
        if body:
            DisputeMessage.objects.create(dispute=d, author=actor, body=body)
        _attach_evidence(d, actor, evidence)
        waiting_for_me = (d.status == D.WAITING_SELLER and role == "seller") or (d.status == D.WAITING_BUYER and role == "buyer") \
            or d.status == D.EVIDENCE_REQUESTED
        if waiting_for_me:
            d.response_due_at = None
            d.save(update_fields=["response_due_at", "updated_at"])
            _set_status(d, D.UNDER_REVIEW, actor=actor, comment=f"ответ стороны ({role})")
        record(action="dispute.party_reply", subject_type="dispute", subject_id=d.pk, actor=actor, order_id=d.order_id)
    if d.assignee_id:
        notify(d.assignee, "dispute.reply", "Новый ответ в споре", body[:120], dispute=d.pk, order=d.order_id)
    return d


def appeal(dispute_id, *, actor, reason: str) -> Dispute:
    from payments.services import suspend_payout

    reason = (reason or "").strip()
    if len(reason) < MIN_DESCRIPTION:
        raise DomainError("Опишите основания апелляции", code="description_required", status_code=400)
    with transaction.atomic():
        d = Dispute.objects.select_for_update().select_related("order").get(pk=dispute_id)
        _role(d.order, actor)
        if d.status not in (D.RESOLVED, D.REJECTED):
            raise DomainError("Апелляция возможна только на принятое решение", code="not_appealable")
        if d.appeal_of_id or d.appeals.exists():
            raise DomainError("Апелляция по этому спору уже подавалась", code="appeal_used")
        if d.resolved_at and timezone.now() - d.resolved_at > timedelta(days=APPEAL_DAYS):
            raise DomainError("Срок апелляции истёк", code="appeal_window_passed")
        _set_status(d, D.APPEALED, actor=actor, comment="подана апелляция")
        a = Dispute.objects.create(order=d.order, opened_by=actor, reason=d.reason, description=reason, appeal_of=d,
                                   status=D.APPEALED, priority=Dispute.Priority.HIGH)
        order = Order.objects.select_for_update().get(pk=d.order_id)
        for di in d.items.select_related("order_item"):
            it = OrderItem.objects.select_for_update().get(pk=di.order_item_id)
            DisputeItem.objects.create(dispute=a, order_item=it, status_before=it.status)
            if it.status != S.DISPUTED and can_transition(it.status, S.DISPUTED):
                _move(order, it, S.DISPUTED, actor=actor, event="item.appealed", dispute=a.pk)
            suspend_payout(it, reason=f"appeal {a.pk}")
        append_event(order, "dispute.appealed", actor=actor, dispute=a.pk, original=d.pk)
    return a


# --- staff --------------------------------------------------------------------------------
def _staff(d: Dispute, actor, perm="dispute.handle"):
    if not actor.has_perm_code(perm):
        raise DomainError("Недостаточно прав", code="forbidden", status_code=403)
    if d.status in (D.ESCALATED, D.APPEALED) and perm in ("dispute.decide",) and not actor.has_perm_code("dispute.escalated"):
        raise DomainError("Эскалированный спор рассматривает старший администратор", code="escalated_only", status_code=403)


def assign(dispute_id, *, actor, assignee) -> Dispute:
    with transaction.atomic():
        d = Dispute.objects.select_for_update().get(pk=dispute_id)
        _staff(d, actor)
        if not assignee.has_perm_code("dispute.handle"):
            raise DomainError("Сотрудник не может вести споры", code="bad_assignee", status_code=400)
        if d.appeal_of_id:
            prev = d.appeal_of.decisions.values_list("decided_by_id", flat=True)
            if assignee.pk in prev:
                raise DomainError("Апелляцию рассматривает другой сотрудник", code="same_reviewer", status_code=400)
        before = str(d.assignee_id) if d.assignee_id else None
        d.assignee = assignee
        d.save(update_fields=["assignee", "updated_at"])
        record(action="dispute.assigned", subject_type="dispute", subject_id=d.pk, actor=actor, is_staff_action=True,
               order_id=d.order_id, before={"assignee": before}, after={"assignee": str(assignee.pk)})
    return d


def set_priority(dispute_id, *, actor, priority: str) -> Dispute:
    with transaction.atomic():
        d = Dispute.objects.select_for_update().get(pk=dispute_id)
        _staff(d, actor)
        if priority not in Dispute.Priority.values:
            raise DomainError("Неверный приоритет", code="bad_priority", status_code=400)
        before = d.priority
        d.priority = priority
        d.save(update_fields=["priority", "updated_at"])
        record(action="dispute.priority", subject_type="dispute", subject_id=d.pk, actor=actor, is_staff_action=True,
               order_id=d.order_id, before={"priority": before}, after={"priority": priority})
    return d


def staff_message(dispute_id, *, actor, body: str, internal: bool) -> DisputeMessage:
    with transaction.atomic():
        d = Dispute.objects.select_for_update().select_related("order").get(pk=dispute_id)
        _staff(d, actor)
        m = DisputeMessage.objects.create(dispute=d, author=actor, body=body.strip(),
                                          visibility=DisputeMessage.Visibility.STAFF if internal else DisputeMessage.Visibility.ALL)
        record(action="dispute.staff_message", subject_type="dispute", subject_id=d.pk, actor=actor, is_staff_action=True,
               order_id=d.order_id, after={"internal": internal})
    if not internal:
        for u in (d.order.buyer, d.order.seller):
            notify(u, "dispute.message", "Сообщение администрации по жалобе", body[:120], dispute=d.pk, order=d.order_id)
    return m


def request_evidence(dispute_id, *, actor, from_party: str, comment: str, hours: int | None = None) -> Dispute:
    if from_party not in ("buyer", "seller", "both"):
        raise DomainError("Укажите сторону", code="bad_party", status_code=400)
    if len((comment or "").strip()) < 3:
        raise DomainError("Комментарий обязателен", code="comment_required", status_code=400)
    with transaction.atomic():
        d = Dispute.objects.select_for_update().select_related("order").get(pk=dispute_id)
        _staff(d, actor)
        d.response_due_at = timezone.now() + timedelta(hours=hours or settings.DISPUTE_RESPONSE_HOURS)
        d.response_overdue = False
        d.save(update_fields=["response_due_at", "response_overdue", "updated_at"])
        _set_status(d, D.EVIDENCE_REQUESTED, actor=actor, comment=comment, staff=True)
        DisputeMessage.objects.create(dispute=d, author=actor, body=f"Запрошены доказательства: {comment}")
        append_event(d.order, "dispute.evidence_requested", actor=actor, dispute=d.pk, party=from_party)
    targets = {"buyer": [d.order.buyer], "seller": [d.order.seller], "both": [d.order.buyer, d.order.seller]}[from_party]
    for u in targets:
        notify(u, "dispute.evidence_requested", "Администратор запросил доказательства", comment, dispute=d.pk, order=d.order_id)
    return d


def escalate(dispute_id, *, actor, comment: str) -> Dispute:
    with transaction.atomic():
        d = Dispute.objects.select_for_update().get(pk=dispute_id)
        _staff(d, actor)
        if len((comment or "").strip()) < 3:
            raise DomainError("Комментарий обязателен", code="comment_required", status_code=400)
        _set_status(d, D.ESCALATED, actor=actor, comment=comment, staff=True)
        d.priority = Dispute.Priority.HIGH
        d.save(update_fields=["priority", "updated_at"])
    return d


def decide(dispute_id, *, actor, item_id, decision_type: str, comment: str, refund_amount_minor: int | None = None,
           new_deadline=None, sanction: dict | None = None) -> DisputeDecision:
    """One decision for one order item (roadmap 9.6). Comment is mandatory; financial decisions need finance.refund."""
    from payments.services import refund_item, resume_payout

    comment = (comment or "").strip()
    if len(comment) < 10:
        raise DomainError("Решение должно сопровождаться комментарием (от 10 символов)", code="comment_required", status_code=400)
    T = DisputeDecision.Type
    if decision_type not in T.values:
        raise DomainError("Неизвестное решение", code="bad_decision", status_code=400)
    if decision_type == T.REQUEST_EVIDENCE:
        request_evidence(dispute_id, actor=actor, from_party="both", comment=comment)
        return DisputeDecision.objects.create(dispute_id=dispute_id, decision_type=decision_type, comment=comment, decided_by=actor)
    if decision_type == T.ESCALATE:
        escalate(dispute_id, actor=actor, comment=comment)
        return DisputeDecision.objects.create(dispute_id=dispute_id, decision_type=decision_type, comment=comment, decided_by=actor)

    with transaction.atomic():
        d = Dispute.objects.select_for_update().select_related("order").get(pk=dispute_id)
        _staff(d, actor, perm="dispute.decide")
        if decision_type in FINANCIAL and not actor.has_perm_code("finance.refund"):
            raise DomainError("Финансовые решения доступны только администратору", code="forbidden", status_code=403)
        if decision_type == T.SANCTION and not actor.has_perm_code("user.sanction"):
            raise DomainError("Недостаточно прав для санкций", code="forbidden", status_code=403)
        reviewable = set(ACTIVE_DISPUTE_STATUSES) - {D.OPEN}
        if decision_type == T.SANCTION:
            reviewable |= {D.RESOLVED, D.REJECTED}  # sanctions may follow the decision (scenarios 7, 10)
        if d.status not in reviewable:
            raise DomainError("Спор не на рассмотрении", code="dispute_not_reviewable")
        if d.appeal_of_id and d.appeal_of.decisions.filter(decided_by=actor).exists():
            raise DomainError("Апелляцию рассматривает другой сотрудник", code="same_reviewer", status_code=403)
        di = d.items.select_for_update().filter(order_item_id=item_id, is_active=True).first()
        if decision_type != T.SANCTION and not di:
            raise DomainError("Позиция не относится к спору или уже решена", code="bad_item", status_code=400)
        if decision_type == T.PARTIAL_REFUND and not refund_amount_minor:
            raise DomainError("Укажите сумму частичного возврата", code="amount_required", status_code=400)
        if decision_type in (T.REDO, T.EXTEND) and not new_deadline:
            raise DomainError("Укажите новый срок", code="deadline_required", status_code=400)

        decision = DisputeDecision.objects.create(
            dispute=d, order_item_id=item_id if di else None, decision_type=decision_type, comment=comment, decided_by=actor,
            refund_amount_minor=refund_amount_minor if decision_type == T.PARTIAL_REFUND else None, new_deadline=new_deadline)
        record(action=f"dispute.decision.{decision_type}", subject_type="dispute", subject_id=d.pk, actor=actor, is_staff_action=True,
               order_id=d.order_id, after={"item": str(item_id) if item_id else None, "amount": refund_amount_minor,
                                           "deadline": str(new_deadline) if new_deadline else None},
               comment=comment)
        order = Order.objects.select_for_update().get(pk=d.order_id)

        if decision_type == T.SANCTION:
            s = sanction or {}
            target_id = order.buyer_id if s.get("target") == "buyer" else order.seller_id
            stype = s.get("type", UserSanction.Type.WARNING)
            if stype not in UserSanction.Type.values:
                raise DomainError("Неверный тип санкции", code="bad_sanction", status_code=400)
            days = s.get("days")
            UserSanction.objects.create(user_id=target_id, type=stype, reason=comment, created_by=actor, dispute=d,
                                        ends_at=timezone.now() + timedelta(days=int(days)) if days else None)
            if stype == UserSanction.Type.BLOCK:
                from accounts.models import User

                User.objects.filter(pk=target_id).update(status=User.Status.BLOCKED)
            elif stype == UserSanction.Type.LIMIT:
                from accounts.models import User

                User.objects.filter(pk=target_id, status=User.Status.ACTIVE).update(status=User.Status.LIMITED)
            DisputeAction.objects.create(decision=decision, action_type="sanction", status=DisputeAction.Status.DONE)
            return decision

        item = OrderItem.objects.select_for_update().get(pk=item_id)
        action = DisputeAction.objects.create(decision=decision, action_type=decision_type)
        before = di.status_before

        if decision_type in FINANCIAL:
            amount = None if decision_type == T.FULL_REFUND else refund_amount_minor
            di.is_active, di.decided = False, True
            di.save(update_fields=["is_active", "decided", "updated_at"])
        elif decision_type == T.REJECT:
            target = S.AWAITING_BUYER_CONFIRMATION if before == S.PUBLISHED else before
            if not can_transition(S.DISPUTED, target):
                target = S.IN_PROGRESS
            if target == S.AWAITING_BUYER_CONFIRMATION:
                item.confirm_deadline = timezone.now() + timedelta(hours=settings.BUYER_CONFIRM_WINDOW_HOURS)
            if target == S.AWAITING_SELLER_ACCEPTANCE:
                item.accept_deadline = timezone.now() + timedelta(hours=settings.SELLER_ACCEPT_TIMEOUT_HOURS)
            _move(order, item, target, actor=actor, event="item.dispute_rejected", dispute=d.pk)
            resume_payout(item)
        elif decision_type in (T.REDO, T.EXTEND):
            item.publish_deadline = new_deadline
            _move(order, item, S.IN_PROGRESS, actor=actor, event=f"item.dispute_{decision_type}", dispute=d.pk,
                  deadline=str(new_deadline))
        elif decision_type == T.IN_FAVOR_OF_SELLER:
            from payments.services import create_payout_hold

            now = timezone.now()
            if not item.confirmed_at:
                item.confirmed_at = now
                item.payout_available_at = now + timedelta(hours=settings.PAYOUT_HOLD_HOURS)
            _move(order, item, S.COMPLETED, actor=actor, event="item.dispute_seller_won", dispute=d.pk)
            create_payout_hold(item)
            resume_payout(item)
        if decision_type not in FINANCIAL:
            di.is_active, di.decided = False, True
            di.save(update_fields=["is_active", "decided", "updated_at"])
            action.status = DisputeAction.Status.DONE
            action.save(update_fields=["status", "updated_at"])

    if decision_type in FINANCIAL:
        try:
            refund = refund_item(item_id, amount_minor=amount, reason=f"Решение по спору: {comment}", actor=actor, decision=decision)
            action.refund_request = refund
            action.status = DisputeAction.Status.DONE if refund and refund.status == "succeeded" else DisputeAction.Status.PENDING
        except DomainError as e:
            action.status, action.error = DisputeAction.Status.FAILED, e.message
            with transaction.atomic():  # the decision stands, but money could not move → item stays in dispute
                DisputeItem.objects.filter(pk=di.pk).update(is_active=True, decided=False)
            action.save(update_fields=["refund_request", "status", "error", "updated_at"])
            raise
        action.save(update_fields=["refund_request", "status", "error", "updated_at"])
        with transaction.atomic():
            it = OrderItem.objects.select_for_update().get(pk=item_id)
            if it.status == S.PARTIALLY_REFUNDED:
                # The seller keeps the undisputed remainder: hold 48h from the decision if never confirmed (D-014)
                from payments.services import create_payout_hold

                if not it.confirmed_at:
                    it.confirmed_at = timezone.now()
                    it.payout_available_at = it.confirmed_at + timedelta(hours=settings.PAYOUT_HOLD_HOURS)
                    it.save(update_fields=["confirmed_at", "payout_available_at", "updated_at"])
                create_payout_hold(it)
                resume_payout(it)
    _maybe_resolve(dispute_id, actor)
    return decision


def _maybe_resolve(dispute_id, actor):
    with transaction.atomic():
        d = Dispute.objects.select_for_update().select_related("order").get(pk=dispute_id)
        if d.items.filter(is_active=True).exists():
            return
        types = set(d.decisions.filter(decision_type__in=FINAL).values_list("decision_type", flat=True))
        dst = D.REJECTED if types == {DisputeDecision.Type.REJECT} else D.RESOLVED
        _set_status(d, dst, actor=actor, comment="все позиции решены", staff=True)
        d.resolved_at = timezone.now()
        d.save(update_fields=["resolved_at", "updated_at"])
        if d.appeal_of_id:
            orig = Dispute.objects.select_for_update().get(pk=d.appeal_of_id)
            _set_status(orig, D.CLOSED, actor=actor, comment="апелляция рассмотрена", staff=True)
            _set_status(d, D.CLOSED, actor=actor, comment="решение по апелляции окончательное", staff=True)
            d.closed_at = timezone.now()
            d.save(update_fields=["closed_at", "updated_at"])
        append_event(Order.objects.select_for_update().get(pk=d.order_id), "dispute.decided", actor=actor, dispute=d.pk, result=dst)
    for u in (d.order.buyer, d.order.seller):
        notify(u, "dispute.decided", "Принято решение по жалобе", "Подробности — в карточке заказа", dispute=d.pk, order=d.order_id)


# --- timers -----------------------------------------------------------------------------
def process_timeouts(now=None) -> int:
    """A side that did not answer in time: mark overdue and move to review. Never decides by itself (9.5)."""
    now = now or timezone.now()
    n = 0
    qs = Dispute.objects.filter(status__in=[D.WAITING_SELLER, D.WAITING_BUYER, D.EVIDENCE_REQUESTED], response_due_at__lt=now)
    for did in qs.values_list("pk", flat=True):
        with transaction.atomic():
            d = Dispute.objects.select_for_update().get(pk=did)
            if d.status not in (D.WAITING_SELLER, D.WAITING_BUYER, D.EVIDENCE_REQUESTED):
                continue
            d.response_overdue = True
            d.save(update_fields=["response_overdue", "updated_at"])
            _set_status(d, D.UNDER_REVIEW, comment="сторона не ответила в срок")
            n += 1
    return n


def close_expired_appeal_windows(now=None) -> int:
    now = now or timezone.now()
    n = 0
    for did in Dispute.objects.filter(status__in=[D.RESOLVED, D.REJECTED], resolved_at__lt=now - timedelta(days=APPEAL_DAYS)).values_list("pk", flat=True):
        with transaction.atomic():
            d = Dispute.objects.select_for_update().get(pk=did)
            _set_status(d, D.CLOSED, comment="срок апелляции истёк")
            d.closed_at = now
            d.save(update_fields=["closed_at", "updated_at"])
            n += 1
    return n


def party_history(user_id) -> dict:
    """For staff: previous disputes of a user (scenario 7: repeated false complaints)."""
    opened = Dispute.objects.filter(opened_by_id=user_id, appeal_of__isnull=True)
    return {
        "opened": opened.count(),
        "rejected": opened.filter(status__in=[D.REJECTED]).count()
        + opened.filter(status=D.CLOSED, decisions__decision_type=DisputeDecision.Type.REJECT).distinct().count(),
        "against": Dispute.objects.filter(appeal_of__isnull=True).filter(order__buyer_id=user_id).exclude(opened_by_id=user_id).count()
        + Dispute.objects.filter(appeal_of__isnull=True).filter(order__seller_id=user_id).exclude(opened_by_id=user_id).count(),
        "sanctions": UserSanction.objects.filter(user_id=user_id, revoked_at__isnull=True).count(),
    }

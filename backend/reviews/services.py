"""Reviews & reputation (roadmap Phase 11).

Rules: a review only after a real completed deal (COMPLETED, or PARTIALLY_REFUNDED = completed with
compensation), one per order item, no review while a dispute is active; a fully refunded item withdraws
its review (as FunPay does on cancellation). A complaint alone never changes the rating.
"""
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.utils import timezone

from audit.services import record
from common.exceptions import DomainError
from notifications.services import notify

from .models import Review, ReviewComplaint

RATED_STATUSES = ["COMPLETED", "PARTIALLY_REFUNDED"]


def _published():
    return Review.objects.filter(moderation_status=Review.Moderation.PUBLISHED, order_item__status__in=RATED_STATUSES)


def seller_rating(user_id) -> dict:
    agg = _published().filter(target_user_id=user_id).aggregate(avg=Avg("rating"), n=Count("id"))
    return {"rating": round(agg["avg"], 2) if agg["avg"] is not None else None, "reviews_count": agg["n"]}


def ratings_for(user_ids) -> dict:
    rows = _published().filter(target_user_id__in=list(user_ids)).values("target_user_id").annotate(avg=Avg("rating"), n=Count("id"))
    return {r["target_user_id"]: {"rating": round(r["avg"], 2), "reviews_count": r["n"]} for r in rows}


def completed_orders_count(user_id) -> int:
    from orders.models import OrderItem

    return OrderItem.objects.filter(order__seller_id=user_id, status__in=RATED_STATUSES).count()


def create_review(order_id, item_id, *, actor, rating: int, text: str) -> Review:
    from orders.models import OrderItem
    from support.models import DisputeItem

    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise DomainError("Оценка от 1 до 5", code="bad_rating", status_code=400)
    with transaction.atomic():
        item = OrderItem.objects.select_for_update().select_related("order").filter(pk=item_id, order_id=order_id).first()
        if not item or item.order.buyer_id != actor.pk:
            raise DomainError("Нет доступа", code="forbidden", status_code=404)
        if DisputeItem.objects.filter(order_item=item, is_active=True).exists():
            raise DomainError("Дождитесь решения по жалобе", code="dispute_active")
        if item.status not in RATED_STATUSES:
            raise DomainError("Отзыв можно оставить после завершения заказа", code="not_completed")
        try:
            with transaction.atomic():
                r = Review.objects.create(order_item=item, author=actor, target_user_id=item.order.seller_id, rating=rating,
                                          text=(text or "").strip()[:4000])
        except IntegrityError as e:
            raise DomainError("Отзыв по этому заказу уже оставлен", code="review_exists") from e
        record(action="review.created", subject_type="review", subject_id=r.pk, actor=actor, order_id=item.order_id, after={"rating": rating})
    notify(item.order.seller, "review.new", "Новый отзыв", f"Оценка {rating}★", order=item.order_id)
    return r


def reply(review_id, *, actor, text: str) -> Review:
    with transaction.atomic():
        r = Review.objects.select_for_update().get(pk=review_id)
        if r.target_user_id != actor.pk:
            raise DomainError("Отвечает только продавец", code="forbidden", status_code=403)
        if r.seller_reply:
            raise DomainError("Ответ уже дан", code="reply_exists")
        if len((text or "").strip()) < 2:
            raise DomainError("Пустой ответ", code="empty", status_code=400)
        r.seller_reply = text.strip()[:4000]
        r.save(update_fields=["seller_reply", "updated_at"])
        record(action="review.replied", subject_type="review", subject_id=r.pk, actor=actor)
    return r


def complain(review_id, *, actor, reason: str) -> ReviewComplaint:
    r = Review.objects.select_related("order_item__order").get(pk=review_id)
    if actor.pk not in (r.author_id, r.target_user_id):
        raise DomainError("Жаловаться могут участники сделки", code="forbidden", status_code=403)
    if len((reason or "").strip()) < 10:
        raise DomainError("Опишите причину жалобы", code="reason_required", status_code=400)
    if ReviewComplaint.objects.filter(review=r, author=actor, status=ReviewComplaint.Status.OPEN).exists():
        raise DomainError("Жалоба уже на рассмотрении", code="complaint_exists")
    c = ReviewComplaint.objects.create(review=r, author=actor, reason=reason.strip()[:2000])
    record(action="review.complaint", subject_type="review", subject_id=r.pk, actor=actor)
    return c  # the review stays published until a moderator decides


def moderate(review_id, *, actor, action: str, comment: str, complaint_id=None) -> Review:
    if not actor.has_perm_code("moderation.content"):
        raise DomainError("Недостаточно прав", code="forbidden", status_code=403)
    if len((comment or "").strip()) < 5:
        raise DomainError("Комментарий обязателен", code="comment_required", status_code=400)
    with transaction.atomic():
        r = Review.objects.select_for_update().get(pk=review_id)
        before = r.moderation_status
        if action == "hide":
            r.moderation_status = Review.Moderation.HIDDEN
        elif action == "restore":
            r.moderation_status = Review.Moderation.PUBLISHED
        elif action != "keep":
            raise DomainError("Неизвестное действие", code="bad_action", status_code=400)
        r.save(update_fields=["moderation_status", "updated_at"])
        qs = r.complaints.filter(status=ReviewComplaint.Status.OPEN)
        if complaint_id:
            qs = qs.filter(pk=complaint_id)
        qs.update(status=ReviewComplaint.Status.ACCEPTED if action == "hide" else ReviewComplaint.Status.REJECTED, updated_at=timezone.now())
        record(action=f"review.{action}", subject_type="review", subject_id=r.pk, actor=actor, is_staff_action=True,
               before={"status": before}, after={"status": r.moderation_status}, comment=comment)
    return r


def withdraw_for_refunded_item(item):
    """Fully refunded deal → its review no longer counts (FunPay: cancellation removes the review)."""
    Review.objects.filter(order_item=item, moderation_status=Review.Moderation.PUBLISHED).update(
        moderation_status=Review.Moderation.WITHDRAWN, updated_at=timezone.now())

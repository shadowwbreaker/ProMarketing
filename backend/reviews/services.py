from django.db.models import Avg, Count

from .models import Review


def seller_rating(user_id) -> dict:
    """Rating from published reviews of real completed deals only (roadmap Phase 11 rule).
    A complaint by itself never lowers the rating."""
    agg = Review.objects.filter(target_user_id=user_id, moderation_status=Review.Moderation.PUBLISHED,
                                order_item__status="COMPLETED").aggregate(avg=Avg("rating"), n=Count("id"))
    return {"rating": round(agg["avg"], 2) if agg["avg"] is not None else None, "reviews_count": agg["n"]}


def ratings_for(user_ids) -> dict:
    rows = (Review.objects.filter(target_user_id__in=list(user_ids), moderation_status=Review.Moderation.PUBLISHED,
                                  order_item__status="COMPLETED")
            .values("target_user_id").annotate(avg=Avg("rating"), n=Count("id")))
    return {r["target_user_id"]: {"rating": round(r["avg"], 2), "reviews_count": r["n"]} for r in rows}


def completed_orders_count(user_id) -> int:
    from orders.models import OrderItem

    return OrderItem.objects.filter(order__seller_id=user_id, status="COMPLETED").count()


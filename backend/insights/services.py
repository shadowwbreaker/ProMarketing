"""Phase 13: favorites, history, recommendations, comparison, order analytics, result reports, referrals."""
import secrets
from datetime import timedelta


from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone

from common.exceptions import DomainError

from .models import Favorite, PublicationMetric, Referral, ReferralCode, ViewedOffer

OFFSETS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}


# --- result reports (D-018) --------------------------------------------------------------
def plan_checkpoints(item):
    """Called once when the seller submits the publication proof for an order with results_report=True.
    Exactly three one-off checks per item; never rescheduled, never extended — not monitoring."""
    if not item.published_at:
        return
    for cp, delta in OFFSETS.items():
        PublicationMetric.objects.get_or_create(order_item=item, checkpoint=cp, defaults={"due_at": item.published_at + delta})


def collect_due_metrics(now=None, limit: int = 200) -> int:
    from social_data.core import errors
    from social_data.core.registry import get_provider
    from social_data.services.refresh_service import credentials_for

    now = now or timezone.now()
    done = 0
    for m in PublicationMetric.objects.filter(status=PublicationMetric.Status.PENDING, due_at__lte=now).select_related(
            "order_item__social_account")[:limit]:
        item = m.order_item
        proof = item.proofs.order_by("-created_at").first()
        from payments.services import refunded_amount

        if not proof or item.status in ("REFUNDED", "CANCELLED", "EXPIRED") or refunded_amount(item.pk) >= item.price_minor:
            m.status = PublicationMetric.Status.SKIPPED
        else:
            try:
                v = get_provider(item.social_account.platform).get_video_statistics(
                    proof.video_url, credentials=credentials_for(item.social_account))
                if v:
                    m.status, m.views, m.likes, m.comments = PublicationMetric.Status.DONE, v.views, v.likes, v.comments
                else:
                    m.status, m.error = PublicationMetric.Status.UNAVAILABLE, "not_found"
            except errors.ProviderError as e:
                m.status, m.error = PublicationMetric.Status.UNAVAILABLE, e.code
        m.fetched_at = now
        m.save()
        done += 1
    return done


def result_report(item) -> dict:
    metrics = {m.checkpoint: m for m in item.metrics.all()}
    exp = item.expected_avg_views
    rows = []
    for cp in OFFSETS:
        m = metrics.get(cp)
        views = m.views if m and m.status == "done" else None
        rows.append({"checkpoint": cp, "status": m.status if m else "not_requested", "views": views,
                     "vs_expected_pct": round(views * 100 / exp) if views is not None and exp else None})
    return {"expected_avg_views": exp, "expected_followers": item.expected_followers,
            "expected_trust_status": item.expected_trust_status, "checkpoints": rows}


# --- favorites & history ---------------------------------------------------------------------
def toggle_favorite(user, *, account_id=None, network_id=None) -> bool:
    if bool(account_id) == bool(network_id):
        raise DomainError("Укажите аккаунт или сетку", code="bad_target", status_code=400)
    from catalog.public import sellable_accounts, sellable_networks

    if account_id and not sellable_accounts().filter(pk=account_id).exists():
        raise DomainError("Предложение недоступно", code="not_found", status_code=404)
    if network_id and not sellable_networks().filter(pk=network_id).exists():
        raise DomainError("Сетка недоступна", code="not_found", status_code=404)
    qs = Favorite.objects.filter(user=user, social_account_id=account_id, network_id=network_id)
    if qs.exists():
        qs.delete()
        return False
    try:
        Favorite.objects.create(user=user, social_account_id=account_id, network_id=network_id)
    except IntegrityError:
        pass
    return True


def mark_viewed(user, account_id):
    from catalog.public import sellable_accounts

    if sellable_accounts().filter(pk=account_id).exists():
        ViewedOffer.objects.update_or_create(user=user, social_account_id=account_id, defaults={"viewed_at": timezone.now()})


def recommendations(user, limit: int = 12):
    """Same categories/platforms as the user's favorites, views and purchases; verified first; excludes own and seen."""
    from catalog.public import sellable_accounts
    from orders.models import OrderItem

    seen = set(ViewedOffer.objects.filter(user=user).values_list("social_account_id", flat=True))
    fav = set(Favorite.objects.filter(user=user, social_account__isnull=False).values_list("social_account_id", flat=True))
    bought = set(OrderItem.objects.filter(order__buyer=user).values_list("social_account_id", flat=True))
    from social_data.models import SocialAccount

    base = SocialAccount.objects.filter(pk__in=seen | fav | bought)
    cats = [c for c in base.values_list("category", flat=True) if c]
    plats = list(base.values_list("platform", flat=True))
    qs = sellable_accounts().exclude(owner=user).exclude(pk__in=seen | fav | bought)
    if cats or plats:
        qs = qs.filter(Q(category__in=cats) | Q(platform__in=plats))
    return list(qs.order_by(F("current_statistics__trust_status").asc(nulls_last=True), "-current_statistics__avg_views")
                .prefetch_related("offers")[:limit])


# --- analytics -------------------------------------------------------------------------------
def buyer_analytics(user) -> dict:
    from orders.models import Order, OrderItem
    from payments.models import RefundRequest

    paid = Order.objects.filter(buyer=user, paid_at__isnull=False)
    items = OrderItem.objects.filter(order__buyer=user, order__paid_at__isnull=False)
    refunds = RefundRequest.objects.filter(order_item__order__buyer=user, status="succeeded").aggregate(s=Sum("amount_minor"))["s"] or 0
    spent = paid.aggregate(s=Sum("total_minor"))["s"] or 0
    by_status = dict(items.values_list("status").annotate(n=Count("id")))
    reports = PublicationMetric.objects.filter(order_item__order__buyer=user, status="done")
    return {"orders_paid": paid.count(), "spent_minor": spent, "refunded_minor": refunds, "net_spent_minor": spent - refunds,
            "items_by_status": by_status, "avg_item_price_minor": int(items.aggregate(a=Avg("price_minor"))["a"] or 0),
            "views_30d_total": reports.filter(checkpoint="30d").aggregate(s=Sum("views"))["s"] or 0,
            "cost_per_1000_views_minor": _cpm(user)}


def _cpm(user):
    from orders.models import OrderItem

    total_cost = 0
    total_views = 0
    for it in OrderItem.objects.filter(order__buyer=user, metrics__checkpoint="30d", metrics__status="done").distinct():
        m = it.metrics.get(checkpoint="30d")
        total_cost += it.price_minor
        total_views += m.views or 0
    return round(total_cost * 1000 / total_views) if total_views else None


def seller_analytics(user) -> dict:
    from orders.models import OrderItem
    from support.models import Dispute

    items = OrderItem.objects.filter(order__seller=user, order__paid_at__isnull=False)
    done = items.filter(status__in=["COMPLETED", "PARTIALLY_REFUNDED"])
    accepted = items.filter(accepted_at__isnull=False)
    accept_hours = [(i.accepted_at - i.order.paid_at).total_seconds() / 3600 for i in accepted.select_related("order")]
    return {"items_total": items.count(), "items_completed": done.count(),
            "completion_rate_pct": round(done.count() * 100 / items.count()) if items.count() else None,
            "revenue_minor": done.aggregate(s=Sum("seller_amount_minor"))["s"] or 0,
            "expired_or_declined": items.filter(status__in=["EXPIRED"]).count() + items.filter(events__type="item.declined_by_seller").distinct().count(),
            "disputes": Dispute.objects.filter(order__seller=user, appeal_of__isnull=True).count(),
            "avg_accept_hours": round(sum(accept_hours) / len(accept_hours), 1) if accept_hours else None,
            "by_account": list(done.values("social_account__title").annotate(n=Count("id"), revenue=Sum("seller_amount_minor"))
                               .order_by("-revenue")[:20])}


# --- referrals ---------------------------------------------------------------------------------
def referral_code(user) -> str:
    rc = ReferralCode.objects.filter(user=user).first()
    if rc:
        return rc.code
    for _ in range(5):
        try:
            return ReferralCode.objects.create(user=user, code=secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")[:8]).code
        except IntegrityError:
            continue
    raise DomainError("Не удалось создать код", code="referral_code_error")


@transaction.atomic
def attach_referral(new_user, code: str):
    if not code:
        return None
    rc = ReferralCode.objects.filter(code=code.strip()).select_related("user").first()
    if not rc or rc.user_id == new_user.pk:
        return None
    return Referral.objects.get_or_create(referred=new_user, defaults={"referrer": rc.user})[0]


def referral_stats(user) -> dict:
    from orders.models import OrderItem

    refs = Referral.objects.filter(referrer=user)
    ids = list(refs.values_list("referred_id", flat=True))
    return {"code": referral_code(user), "invited": len(ids),
            "invited_with_completed_deals": OrderItem.objects.filter(Q(order__buyer_id__in=ids) | Q(order__seller_id__in=ids),
                                                                     status="COMPLETED").values("order__buyer_id").distinct().count(),
            "reward_policy": "Вознаграждение не начисляется: модель финансирования не утверждена (Q-10)."}




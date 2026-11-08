"""Public catalog (roadmap Phase 5). Read-only, anonymous access.

Only sellable items are shown: listed + active account, enabled platform, active offer, seller not blocked.
YouTube averages are hidden until derived metrics are approved (D-016) — also excluded from avg filters.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Exists, Min, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.avatar import avatar_url
from accounts.models import User
from common.exceptions import DomainError
from common.pagination import StandardPagination
from reviews.models import Review
from reviews.services import completed_orders_count, ratings_for, seller_rating
from social_data.core.registry import platform_enabled
from social_data.models import SocialAccount
from social_data.services.refresh_service import display_status

from .models import AccountNetwork, AdvertisingOffer, NetworkItem
from .services import network_stats

SORTS = {
    "new": "-created_at",
    "price_asc": "min_price",
    "price_desc": "-min_price",
    "followers": "-current_statistics__followers",
    "views": "-current_statistics__avg_views",
    "popular": "-completed_count",
}


ONLINE_WINDOW = timedelta(minutes=10)


def seller_brief(user, ratings: dict) -> dict:
    """Seller as shown next to an offer: name, photo, rating, online, time on the platform."""
    r = ratings.get(user.pk, {"rating": None, "reviews_count": 0})
    return {"id": str(user.pk), "display_name": user.profile.display_name, "avatar_url": avatar_url(user.profile),
            "online": bool(user.last_seen_at and timezone.now() - user.last_seen_at < ONLINE_WINDOW),
            "member_since": user.date_joined, **r}


def enabled_platforms() -> list[str]:
    return [p for p in ("tiktok", "instagram", "youtube") if platform_enabled(p)]


def sellable_accounts():
    active_offers = AdvertisingOffer.objects.filter(social_account=OuterRef("pk"), is_active=True)
    return (
        SocialAccount.objects.filter(is_listed=True, status=SocialAccount.Status.ACTIVE, platform__in=enabled_platforms(),
                                     owner__is_active=True, owner__status=User.Status.ACTIVE)
        .filter(Exists(active_offers))
        .annotate(min_price=Subquery(active_offers.order_by("price_minor").values("price_minor")[:1]),
                  completed_count=Count("order_items", filter=Q(order_items__status="COMPLETED"), distinct=True))
        .select_related("current_statistics", "owner__profile")
    )


def _int(params, key):
    v = params.get(key)
    if v in (None, ""):
        return None
    try:
        return int(v)
    except ValueError as e:
        raise DomainError(f"Параметр {key} должен быть числом", code="bad_filter", status_code=400) from e


def apply_filters(qs, params):
    """Filters (roadmap 5.3); all combine with AND."""
    if p := params.get("platform"):
        qs = qs.filter(platform__in=p.split(","))
    if (v := _int(params, "followers_min")) is not None:
        qs = qs.filter(current_statistics__followers__gte=v)
    if (v := _int(params, "followers_max")) is not None:
        qs = qs.filter(current_statistics__followers__lte=v)
    yt_hidden = not settings.YOUTUBE_DERIVED_METRICS_APPROVED
    avg_min, avg_max = _int(params, "avg_min"), _int(params, "avg_max")
    if avg_min is not None or avg_max is not None:
        if yt_hidden:  # YouTube averages are not public → cannot be filtered on
            qs = qs.exclude(Q(platform="youtube") & ~Q(current_statistics__source="manual"))
        if avg_min is not None:
            qs = qs.filter(current_statistics__avg_views__gte=avg_min)
        if avg_max is not None:
            qs = qs.filter(current_statistics__avg_views__lte=avg_max)
    if (v := _int(params, "price_min")) is not None:
        qs = qs.filter(min_price__gte=v)
    if (v := _int(params, "price_max")) is not None:
        qs = qs.filter(min_price__lte=v)
    if c := params.get("category"):
        qs = qs.filter(category__iexact=c)
    if lang := params.get("language"):
        qs = qs.filter(language__iexact=lang)
    if geo := params.get("geo"):
        qs = qs.filter(geo__icontains=geo)
    if fmt := params.get("ad_format"):
        qs = qs.filter(offers__ad_format__in=fmt.split(","), offers__is_active=True).distinct()
    if params.get("verified") == "1":
        fresh = timezone.now() - timedelta(days=settings.STATS_STALE_AFTER_DAYS)
        qs = qs.filter(current_statistics__trust_status="VERIFIED", current_statistics__fetched_at__gte=fresh)
    if params.get("online") == "1":
        qs = qs.filter(owner__last_seen_at__gte=timezone.now() - ONLINE_WINDOW)
    if (v := params.get("rating_min")) not in (None, ""):
        try:
            rmin = float(v)
        except ValueError as e:
            raise DomainError("rating_min должен быть числом", code="bad_filter", status_code=400) from e
        good = (Review.objects.filter(moderation_status="published", order_item__status__in=["COMPLETED", "PARTIALLY_REFUNDED"])
                .values("target_user_id").annotate(n=Count("id")))
        from django.db.models import Avg

        ok_ids = [r["target_user_id"] for r in good.annotate(a=Avg("rating")).filter(a__gte=rmin)]
        qs = qs.filter(owner_id__in=ok_ids)
    if q := (params.get("q") or "").strip():
        qs = qs.filter(Q(title__icontains=q) | Q(handle__icontains=q) | Q(description__icontains=q) | Q(category__icontains=q))
    return qs


def offer_card(acc: SocialAccount, ratings: dict, *, with_offers=False) -> dict:
    offers = [o for o in acc.offers.all() if o.is_active]
    st = display_status(acc.current_statistics, acc.platform, for_owner=False)
    card = {
        "id": str(acc.pk), "title": acc.title, "platform": acc.platform, "handle": acc.handle, "profile_url": acc.profile_url,
        "category": acc.category, "language": acc.language, "geo": acc.geo,
        "followers": st["followers"], "avg_views": st["avg_views"], "videos_in_sample": st["videos_in_sample"],
        "stats_updated_at": st["fetched_at"], "trust_status": st["trust_status"], "ownership_verified": acc.ownership_verified,
        "min_price_minor": min((o.price_minor for o in offers), default=None), "currency": "RUB",
        "formats": sorted({o.get_ad_format_display() for o in offers}),
        "seller": seller_brief(acc.owner, ratings),
    }
    if with_offers:
        card["description"] = acc.description
        card["offers"] = [{"id": str(o.pk), "ad_format": o.ad_format, "ad_format_label": o.get_ad_format_display(),
                           "price_minor": o.price_minor, "conditions": o.conditions, "placement_days": o.placement_days,
                           "publish_within_days": o.publish_within_days} for o in offers]
    if st.get("derived_metrics_note"):
        card["derived_metrics_note"] = st["derived_metrics_note"]
    return card


def network_card(net: AccountNetwork, ratings: dict) -> dict:
    return {"id": str(net.pk), "title": net.title, "description": net.description, "conditions": net.conditions,
            "allow_partial_purchase": net.allow_partial_purchase, "stats": network_stats(net, for_owner=False),
            "platforms": sorted({i.social_account.platform for i in net.items.all()}),
            "seller": seller_brief(net.owner, ratings)}


def sellable_networks():
    """A network is sellable only if every account in it is sellable."""
    ok_accounts = sellable_accounts().values("pk")
    bad_items = NetworkItem.objects.filter(network=OuterRef("pk")).filter(
        Q(offer__is_active=False) | ~Q(social_account__in=ok_accounts))
    return (AccountNetwork.objects.filter(is_active=True, owner__status=User.Status.ACTIVE)
            .annotate(n_items=Count("items")).filter(n_items__gte=2).exclude(Exists(bad_items))
            .select_related("owner__profile").prefetch_related("items__social_account__current_statistics"))


class CatalogAccounts(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        qs = apply_filters(sellable_accounts(), request.query_params).prefetch_related("offers")
        sort = SORTS.get(request.query_params.get("sort", "new"), "-created_at")
        qs = qs.order_by(sort, "-created_at")
        pager = StandardPagination()
        page = pager.paginate_queryset(qs, request, view=self)
        ratings = ratings_for({a.owner_id for a in page})
        return pager.get_paginated_response([offer_card(a, ratings) for a in page])


class CatalogCounts(APIView):
    """Counts for the platform bubbles at the top of the catalog."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        rows = dict(sellable_accounts().order_by().values_list("platform").annotate(n=Count("id", distinct=True)))
        return Response({"accounts": sum(rows.values()), "tiktok": rows.get("tiktok", 0), "youtube": rows.get("youtube", 0),
                         "networks": sellable_networks().count()})


class CatalogAccountDetail(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        acc = get_object_or_404(sellable_accounts().prefetch_related("offers"), pk=pk)
        return Response(offer_card(acc, ratings_for([acc.owner_id]), with_offers=True))


class CatalogNetworks(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        qs = sellable_networks().order_by("-created_at")
        if p := request.query_params.get("platform"):
            qs = qs.filter(items__social_account__platform__in=p.split(",")).distinct()
        if request.query_params.get("online") == "1":
            qs = qs.filter(owner__last_seen_at__gte=timezone.now() - ONLINE_WINDOW)
        pager = StandardPagination()
        page = pager.paginate_queryset(qs, request, view=self)
        ratings = ratings_for({n.owner_id for n in page})
        return pager.get_paginated_response([network_card(n, ratings) for n in page])


class CatalogNetworkDetail(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        net = get_object_or_404(sellable_networks(), pk=pk)
        ratings = ratings_for([net.owner_id])
        card = network_card(net, ratings)
        card["items"] = [{"id": str(i.pk), "price_minor": i.price_minor, "offer": str(i.offer_id),
                          "account": offer_card(i.social_account, ratings)} for i in net.items.all()]
        return Response(card)


class CatalogHome(APIView):
    """Home page blocks (roadmap 5.1)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        base = sellable_accounts().prefetch_related("offers")
        popular = list(base.order_by("-completed_count", "-created_at")[:8])
        new = list(base.order_by("-created_at")[:8])
        recommended = list(base.filter(current_statistics__trust_status="VERIFIED")
                           .order_by("-current_statistics__avg_views")[:8])
        nets = list(sellable_networks().annotate(done=Count("orders", filter=Q(orders__status="COMPLETED")))
                    .order_by("-done", "-created_at")[:4])
        owners = {a.owner_id for a in popular + new + recommended} | {n.owner_id for n in nets}
        ratings = ratings_for(owners)
        categories = list(sellable_accounts().exclude(category="").values("category")
                          .annotate(count=Count("pk", distinct=True)).order_by("-count")[:12])
        return Response({
            "popular": [offer_card(a, ratings) for a in popular],
            "new": [offer_card(a, ratings) for a in new],
            "recommended": [offer_card(a, ratings) for a in recommended],
            "networks": [network_card(n, ratings) for n in nets],
            "categories": categories,
            "platforms": enabled_platforms(),
        })


class SellerPage(APIView):
    """Public seller page (roadmap 5.5). Only public information."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        seller = get_object_or_404(User.objects.select_related("profile"), pk=pk, is_active=True, status=User.Status.ACTIVE)
        accounts = list(sellable_accounts().filter(owner=seller).prefetch_related("offers"))
        nets = list(sellable_networks().filter(owner=seller))
        rating = seller_rating(seller.pk)
        reviews = (Review.objects.filter(target_user=seller, moderation_status="published", order_item__status__in=["COMPLETED", "PARTIALLY_REFUNDED"])
                   .select_related("author__profile").order_by("-created_at")[:20])
        ratings = {seller.pk: rating}
        first_listed = SocialAccount.objects.filter(owner=seller).aggregate(m=Min("created_at"))["m"]
        dist = dict(Review.objects.filter(target_user=seller, moderation_status="published",
                                          order_item__status__in=["COMPLETED", "PARTIALLY_REFUNDED"])
                    .values_list("rating").annotate(n=Count("id")).values_list("rating", "n"))
        online = bool(seller.last_seen_at and timezone.now() - seller.last_seen_at < timedelta(minutes=10))
        return Response({
            "rating_distribution": {str(k): dist.get(k, 0) for k in (5, 4, 3, 2, 1)}, "online": online,
            "is_seller": seller.has_role("seller"),
            "id": str(seller.pk), "display_name": seller.profile.display_name, "bio": seller.profile.bio,
            "avatar_url": avatar_url(seller.profile),
            "member_since": seller.date_joined, "last_seen_at": seller.last_seen_at, "selling_since": first_listed,
            "completed_orders": completed_orders_count(seller.pk), **rating,
            "accounts": [offer_card(a, ratings) for a in accounts],
            "networks": [network_card(n, ratings) for n in nets],
            "reviews": [{"id": str(r.pk), "rating": r.rating, "text": r.text, "seller_reply": r.seller_reply,
                         "author": r.author.profile.display_name, "created_at": r.created_at} for r in reviews],
        })

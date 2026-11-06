from datetime import timedelta

import pytest
from django.utils import timezone

from catalog.models import AccountNetwork, NetworkItem


@pytest.fixture
def seller(user_factory):
    return user_factory(roles=("buyer", "seller"))


def listed(account_factory, offer_factory, owner, price=500_000, fmt="integration", **kw):
    acc = account_factory(owner, listed=True, **kw)
    offer_factory(acc, price_minor=price, ad_format=fmt)
    return acc


def ids(resp):
    return {r["id"] for r in resp.json()["results"]}


@pytest.mark.django_db
def test_only_sellable_offers_visible(api, seller, user_factory, account_factory, offer_factory):
    ok = listed(account_factory, offer_factory, seller)
    not_listed = account_factory(seller)
    offer_factory(not_listed)
    no_offer = account_factory(seller, listed=True)
    inactive = account_factory(seller, listed=True)
    offer_factory(inactive, is_active=False)
    review = listed(account_factory, offer_factory, seller, status="under_review")
    insta = listed(account_factory, offer_factory, seller, platform="instagram")  # D-013 disabled
    blocked_owner = user_factory(roles=("seller",), status="blocked")
    by_blocked = listed(account_factory, offer_factory, blocked_owner)
    r = api.get("/api/v1/catalog/accounts")  # anonymous
    assert r.status_code == 200
    assert ids(r) == {str(ok.pk)}
    for hidden in (not_listed, no_offer, inactive, review, insta, by_blocked):
        assert api.get(f"/api/v1/catalog/accounts/{hidden.pk}").status_code == 404
    card = api.get(f"/api/v1/catalog/accounts/{ok.pk}").json()
    for key in ("title", "platform", "profile_url", "followers", "avg_views", "videos_in_sample", "stats_updated_at",
                "trust_status", "min_price_minor", "formats", "offers", "seller"):
        assert key in card, key  # roadmap 5.4 card fields
    assert card["offers"][0]["conditions"] == "" and card["seller"]["rating"] is None


@pytest.mark.django_db
def test_filters_combine(api, seller, account_factory, offer_factory):
    a = listed(account_factory, offer_factory, seller, price=300_000, followers=20_000, avg_views=5_000, category="Еда", geo="Москва")
    b = listed(account_factory, offer_factory, seller, price=900_000, followers=200_000, avg_views=50_000, category="Еда", geo="Казань",
               fmt="mention")
    c = listed(account_factory, offer_factory, seller, price=600_000, followers=100_000, avg_views=30_000, category="Игры",
               trust="MANUAL", language="en")
    g = "/api/v1/catalog/accounts"
    assert ids(api.get(g, {"category": "еда"})) == {str(a.pk), str(b.pk)}
    assert ids(api.get(g, {"category": "еда", "price_max": 500_000})) == {str(a.pk)}
    assert ids(api.get(g, {"followers_min": 50_000, "avg_max": 40_000})) == {str(c.pk)}
    assert ids(api.get(g, {"ad_format": "mention"})) == {str(b.pk)}
    assert ids(api.get(g, {"verified": "1"})) == {str(a.pk), str(b.pk)}
    assert ids(api.get(g, {"language": "en"})) == {str(c.pk)}
    assert ids(api.get(g, {"geo": "казан"})) == {str(b.pk)}
    assert ids(api.get(g, {"q": "Игры"})) == {str(c.pk)}
    assert ids(api.get(g, {"platform": "youtube"})) == set()
    order = [r["id"] for r in api.get(g, {"sort": "price_asc"}).json()["results"]]
    assert order == [str(a.pk), str(c.pk), str(b.pk)]
    assert api.get(g, {"price_min": "abc"}).json()["error"]["code"] == "bad_filter"


@pytest.mark.django_db
def test_stale_not_in_verified_filter(api, seller, account_factory, offer_factory):
    from social_data.models import SocialAccountStatistics

    acc = listed(account_factory, offer_factory, seller)
    SocialAccountStatistics.objects.filter(pk=acc.current_statistics_id).update(
        fetched_at=timezone.now() - timedelta(days=40), expires_at=timezone.now() - timedelta(days=10))
    assert ids(api.get("/api/v1/catalog/accounts", {"verified": "1"})) == set()
    assert api.get(f"/api/v1/catalog/accounts/{acc.pk}").json()["trust_status"] == "STALE"


@pytest.mark.django_db
def test_youtube_average_hidden_and_not_filterable(api, seller, account_factory, offer_factory, settings):
    settings.YOUTUBE_DERIVED_METRICS_APPROVED = False
    yt = listed(account_factory, offer_factory, seller, platform="youtube", avg_views=90_000)
    card = api.get(f"/api/v1/catalog/accounts/{yt.pk}").json()
    assert card["avg_views"] is None and card["trust_status"] == "UNAVAILABLE" and card["followers"] == 50_000
    assert ids(api.get("/api/v1/catalog/accounts", {"avg_min": 1})) == set()
    assert ids(api.get("/api/v1/catalog/accounts", {"verified": "1"})) == set()
    settings.YOUTUBE_DERIVED_METRICS_APPROVED = True
    assert api.get(f"/api/v1/catalog/accounts/{yt.pk}").json()["avg_views"] == 90_000


@pytest.mark.django_db
def test_networks_in_catalog_only_when_all_items_sellable(api, seller, account_factory, offer_factory):
    accs = [listed(account_factory, offer_factory, seller) for _ in range(3)]
    net = AccountNetwork.objects.create(owner=seller, title="Сетка")
    for a in accs:
        NetworkItem.objects.create(network=net, social_account=a, offer=a.offers.first(), price_minor=100_000)
    assert ids(api.get("/api/v1/catalog/networks")) == {str(net.pk)}
    detail = api.get(f"/api/v1/catalog/networks/{net.pk}").json()
    assert detail["stats"]["accounts"] == 3 and len(detail["items"]) == 3
    accs[0].is_listed = False
    accs[0].save()
    assert ids(api.get("/api/v1/catalog/networks")) == set()
    assert api.get(f"/api/v1/catalog/networks/{net.pk}").status_code == 404


@pytest.mark.django_db
def test_home_and_seller_page(api, seller, user_factory, account_factory, offer_factory):
    from orders.models import Order, OrderItem
    from reviews.models import Review

    acc = listed(account_factory, offer_factory, seller, category="Еда")
    buyer = user_factory()
    order = Order.objects.create(buyer=buyer, seller=seller, fee_bps=500, status="COMPLETED", total_minor=500_000)
    item = OrderItem.objects.create(order=order, social_account=acc, offer=acc.offers.first(), price_minor=500_000, status="COMPLETED")
    Review.objects.create(order_item=item, author=buyer, target_user=seller, rating=4, text="ок")
    other_item_order = Order.objects.create(buyer=buyer, seller=seller, fee_bps=500, status="REFUNDED", total_minor=500_000)
    refunded = OrderItem.objects.create(order=other_item_order, social_account=acc, offer=acc.offers.first(), price_minor=500_000,
                                        status="REFUNDED")
    Review.objects.create(order_item=refunded, author=buyer, target_user=seller, rating=1)  # not a completed deal → ignored

    home = api.get("/api/v1/catalog/home").json()
    assert home["popular"][0]["id"] == str(acc.pk)
    assert home["categories"] == [{"category": "Еда", "count": 1}]
    assert home["platforms"] == ["tiktok", "youtube"]

    page = api.get(f"/api/v1/sellers/{seller.pk}").json()
    assert page["completed_orders"] == 1 and page["rating"] == 4.0 and page["reviews_count"] == 1
    assert len(page["accounts"]) == 1 and "email" not in page
    assert api.get(f"/api/v1/sellers/{user_factory(status='blocked').pk}").status_code == 404

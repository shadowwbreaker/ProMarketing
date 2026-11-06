import pytest

from catalog.models import NetworkItem


@pytest.fixture
def seller(user_factory):
    return user_factory(roles=("buyer", "seller"))


@pytest.mark.django_db
def test_offer_create_update_and_format_uniqueness(api, seller, account_factory):
    acc = account_factory(seller)
    api.force_login(seller)
    r = api.post(f"/api/v1/social-accounts/{acc.pk}/offers", {"ad_format": "integration", "price_minor": 1_500_000,
                                                               "placement_days": 30, "conditions": "без мата"}, format="json")
    assert r.status_code == 201, r.content
    offer_id = r.json()["id"]
    r = api.post(f"/api/v1/social-accounts/{acc.pk}/offers", {"ad_format": "integration", "price_minor": 10_000}, format="json")
    assert r.json()["error"]["code"] == "offer_format_exists"
    assert api.post(f"/api/v1/social-accounts/{acc.pk}/offers", {"ad_format": "integration", "price_minor": 1}, format="json").status_code == 400
    r = api.patch(f"/api/v1/offers/{offer_id}", {"price_minor": 2_000_000}, format="json")
    assert r.json()["price_minor"] == 2_000_000
    assert len(api.get(f"/api/v1/social-accounts/{acc.pk}/offers").json()) == 1
    formats = api.get("/api/v1/ad-formats").json()
    assert len(formats) == 8 and formats[0]["label"] == "Интеграция внутри ролика"


@pytest.mark.django_db
def test_offers_of_other_seller_inaccessible(api, seller, user_factory, account_factory, offer_factory):
    other = user_factory(roles=("seller",))
    acc = account_factory(other)
    offer = offer_factory(acc)
    api.force_login(seller)
    assert api.patch(f"/api/v1/offers/{offer.pk}", {"price_minor": 1000}, format="json").status_code == 404
    assert api.get(f"/api/v1/social-accounts/{acc.pk}/offers").status_code == 404
    assert api.post(f"/api/v1/social-accounts/{acc.pk}/listing", {"listed": True}, format="json").status_code == 404


@pytest.mark.django_db
def test_listing_rules(api, seller, account_factory, offer_factory):
    api.force_login(seller)
    no_stats = account_factory(seller, followers=None)
    r = api.post(f"/api/v1/social-accounts/{no_stats.pk}/listing", {"listed": True}, format="json")
    problems = r.json()["error"]["details"]["problems"]
    assert "получите статистику или введите её вручную" in problems
    assert "добавьте хотя бы одно активное предложение" in problems

    acc = account_factory(seller)
    offer = offer_factory(acc)
    seller.is_email_verified = False
    seller.save()
    assert "подтвердите email" in api.post(f"/api/v1/social-accounts/{acc.pk}/listing", {"listed": True}, format="json").json()["error"]["details"]["problems"]
    seller.is_email_verified = True
    seller.save()
    r = api.post(f"/api/v1/social-accounts/{acc.pk}/listing", {"listed": True}, format="json")
    assert r.status_code == 200 and r.json()["is_listed"] is True

    # deactivating the last active offer removes the account from the catalog automatically
    api.patch(f"/api/v1/offers/{offer.pk}", {"is_active": False}, format="json")
    acc.refresh_from_db()
    assert acc.is_listed is False

    suspicious = account_factory(seller, status="under_review")
    offer_factory(suspicious)
    r = api.post(f"/api/v1/social-accounts/{suspicious.pk}/listing", {"listed": True}, format="json")
    assert r.status_code == 400  # hidden until moderator review (scenario 8)


@pytest.mark.django_db
def test_manual_stats_account_can_be_listed(api, seller, account_factory, offer_factory):
    acc = account_factory(seller, trust="MANUAL")
    offer_factory(acc)
    api.force_login(seller)
    assert api.post(f"/api/v1/social-accounts/{acc.pk}/listing", {"listed": True}, format="json").status_code == 200


@pytest.mark.django_db
def test_edit_account_info(api, seller, account_factory):
    acc = account_factory(seller)
    api.force_login(seller)
    r = api.patch(f"/api/v1/social-accounts/{acc.pk}/manage", {"title": "Новое имя", "geo": "Москва", "category": "еда"}, format="json")
    assert r.status_code == 200 and r.json()["title"] == "Новое имя" and r.json()["geo"] == "Москва"
    r = api.patch(f"/api/v1/social-accounts/{acc.pk}/manage", {"platform": "youtube", "external_id": "hack"}, format="json")
    acc.refresh_from_db()
    assert acc.platform == "tiktok" and acc.external_id.startswith("ext-")  # identity fields are read-only


@pytest.mark.django_db
def test_remove_account_blocked_by_active_orders(api, seller, user_factory, account_factory, offer_factory):
    from orders.models import Order, OrderItem

    acc = account_factory(seller)
    offer = offer_factory(acc)
    buyer = user_factory()
    order = Order.objects.create(buyer=buyer, seller=seller, fee_bps=500, status="IN_PROGRESS", total_minor=offer.price_minor)
    item = OrderItem.objects.create(order=order, social_account=acc, offer=offer, price_minor=offer.price_minor, status="IN_PROGRESS")
    api.force_login(seller)
    assert api.get(f"/api/v1/social-accounts/{acc.pk}/orders").json()[0]["id"] == str(item.pk)
    r = api.delete(f"/api/v1/social-accounts/{acc.pk}/manage")
    assert r.json()["error"]["code"] == "active_orders"
    OrderItem.objects.filter(pk=item.pk).update(status="COMPLETED")
    assert api.delete(f"/api/v1/social-accounts/{acc.pk}/manage").status_code == 204
    acc.refresh_from_db()
    assert acc.status == "removed" and not acc.is_listed and not acc.offers.filter(is_active=True).exists()


@pytest.mark.django_db
def test_networks(api, seller, user_factory, account_factory, offer_factory):
    api.force_login(seller)
    accs = [account_factory(seller, followers=10_000 * (i + 1), avg_views=1_000 * (i + 1)) for i in range(5)]
    offers = [offer_factory(a, price_minor=100_000) for a in accs]
    r = api.post("/api/v1/networks", {"title": "Сетка 5 TikTok", "description": "юмор", "conditions": "общие",
                                      "allow_partial_purchase": True}, format="json")
    assert r.status_code == 201
    net_id = r.json()["id"]
    for o in offers:
        assert api.post(f"/api/v1/networks/{net_id}/items", {"offer": str(o.pk)}, format="json").status_code == 201
    dup = api.post(f"/api/v1/networks/{net_id}/items", {"offer": str(offers[0].pk)}, format="json")
    assert dup.json()["error"]["code"] == "already_in_network"
    other = user_factory(roles=("seller",))
    foreign = offer_factory(account_factory(other))
    assert api.post(f"/api/v1/networks/{net_id}/items", {"offer": str(foreign.pk)}, format="json").json()["error"]["code"] == "not_own_account"

    net = api.get(f"/api/v1/networks/{net_id}").json()
    assert net["stats"] == {"accounts": 5, "total_followers": 150_000, "total_avg_views": 15_000, "accounts_with_avg": 5,
                            "verified_accounts": 5, "items_price_minor": 500_000, "price_minor": 500_000}
    r = api.patch(f"/api/v1/networks/{net_id}", {"total_price_minor": 400_000}, format="json")
    assert r.json()["stats"]["price_minor"] == 400_000  # bundle discount; items keep own prices

    item_id = net["items"][0]["id"]
    assert api.delete(f"/api/v1/networks/{net_id}/items/{item_id}").status_code == 204
    assert NetworkItem.objects.filter(network_id=net_id).count() == 4
    # accounts remain independent entities
    assert all(a.__class__.objects.filter(pk=a.pk).exists() for a in accs)

    api.force_login(other)
    assert api.get(f"/api/v1/networks/{net_id}").status_code == 404
    assert api.delete(f"/api/v1/networks/{net_id}/items/{net['items'][1]['id']}").status_code == 404

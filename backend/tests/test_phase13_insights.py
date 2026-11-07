from datetime import timedelta

import pytest
from django.utils import timezone

from insights.models import PublicationMetric
from tests.test_phase6_orders import TERMS, as_, item_url, pay, to_confirmation


@pytest.fixture(autouse=True)
def fake_social():
    from social_data.core.registry import set_provider_override
    from social_data.providers.fake.provider import FakeProvider

    set_provider_override("tiktok", FakeProvider("tiktok"))
    yield
    set_provider_override("tiktok", None)


def order_with_report(api, market, report=True, idx=0):
    r = as_(api, market["buyer"]).post("/api/v1/orders", {"offer": str(market["offers"][idx].pk), "terms": TERMS,
                                                          "results_report": report}, format="json")
    oid, iid = r.json()["id"], r.json()["items"][0]["id"]
    pay(api, market["buyer"], oid)
    to_confirmation(api, market, oid, iid)
    return oid, iid


@pytest.mark.django_db
def test_order_snapshots_expected_stats(api, market):
    r = as_(api, market["buyer"]).post("/api/v1/orders", {"offer": str(market["offers"][0].pk), "terms": TERMS}, format="json").json()
    it = r["items"][0]
    assert (it["expected_followers"], it["expected_avg_views"], it["expected_trust_status"]) == (50_000, 10_000, "VERIFIED")
    assert r["results_report"] is False


@pytest.mark.django_db
def test_result_report_exactly_three_checks_only_when_opted_in(api, market):
    from insights.services import collect_due_metrics

    _, iid_no = order_with_report(api, market, report=False, idx=1)
    assert not PublicationMetric.objects.filter(order_item_id=iid_no).exists()
    oid, iid = order_with_report(api, market)
    assert set(PublicationMetric.objects.filter(order_item_id=iid).values_list("checkpoint", flat=True)) == {"24h", "7d", "30d"}
    now = timezone.now()
    assert collect_due_metrics(now + timedelta(hours=1)) == 0
    assert collect_due_metrics(now + timedelta(hours=25)) == 1
    assert collect_due_metrics(now + timedelta(days=31)) == 2
    assert collect_due_metrics(now + timedelta(days=400)) == 0  # never rescheduled → no monitoring
    rep = as_(api, market["buyer"]).get(f"/api/v1/orders/{oid}/items/{iid}/report").json()
    assert [c["status"] for c in rep["checkpoints"]] == ["done", "done", "done"]
    assert rep["checkpoints"][0]["vs_expected_pct"] == 10  # fake video 1000 views vs promised 10 000 average
    assert as_(api, market["seller"]).get(f"/api/v1/orders/{oid}/items/{iid}/report").status_code == 200


@pytest.mark.django_db
def test_report_skips_refunded_and_hides_from_strangers(api, market, user_factory):
    from insights.services import collect_due_metrics
    from payments.services import refund_item

    oid, iid = order_with_report(api, market)
    refund_item(iid, amount_minor=None, reason="тест", actor=None)
    collect_due_metrics(timezone.now() + timedelta(days=31))
    assert set(PublicationMetric.objects.filter(order_item_id=iid).values_list("status", flat=True)) == {"skipped"}
    assert as_(api, user_factory()).get(f"/api/v1/orders/{oid}/items/{iid}/report").status_code == 404


@pytest.mark.django_db
def test_favorites_viewed_recommendations(api, market, user_factory, account_factory, offer_factory):
    other_seller = user_factory(roles=("seller",))
    same_cat = account_factory(other_seller, listed=True, category="Еда")
    offer_factory(same_cat)
    first = market["accs"][0]
    first.category = "Еда"
    first.save()
    b = as_(api, market["buyer"])
    assert b.post("/api/v1/me/favorites", {"account": str(first.pk)}, format="json").json()["favorite"] is True
    assert len(b.get("/api/v1/me/favorites").json()["accounts"]) == 1
    assert b.post("/api/v1/me/favorites", {"account": str(first.pk)}, format="json").json()["favorite"] is False
    b.post("/api/v1/me/viewed", {"account": str(first.pk)}, format="json")
    b.post("/api/v1/me/viewed", {"account": str(first.pk)}, format="json")
    assert len(b.get("/api/v1/me/viewed").json()) == 1
    rec_ids = {c["id"] for c in b.get("/api/v1/me/recommendations").json()}
    assert str(same_cat.pk) in rec_ids and str(first.pk) not in rec_ids  # similar, not already seen
    hidden = account_factory(other_seller)  # not listed
    assert b.post("/api/v1/me/favorites", {"account": str(hidden.pk)}, format="json").status_code == 404


@pytest.mark.django_db
def test_compare(api, market):
    ids = ",".join(str(a.pk) for a in market["accs"][:3])
    r = api.get("/api/v1/catalog/compare", {"ids": ids}).json()
    assert [c["id"] for c in r] == ids.split(",") and all("offers" in c for c in r)
    assert api.get("/api/v1/catalog/compare", {"ids": str(market["accs"][0].pk)}).json()["error"]["code"] == "compare_count"


@pytest.mark.django_db
def test_analytics(api, market):
    from insights.services import collect_due_metrics

    oid, iid = order_with_report(api, market)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    collect_due_metrics(timezone.now() + timedelta(days=31))
    b = as_(api, market["buyer"]).get("/api/v1/me/analytics").json()["buyer"]
    assert b["orders_paid"] == 1 and b["spent_minor"] == 100_000 and b["views_30d_total"] == 1000
    assert b["cost_per_1000_views_minor"] == 100_000  # 1000 ₽ per 1000 views
    s = as_(api, market["seller"]).get("/api/v1/me/analytics").json()["seller"]
    assert s["items_completed"] == 1 and s["revenue_minor"] == 95_000 and s["completion_rate_pct"] == 100


@pytest.mark.django_db
def test_referrals(api, user_factory):
    inviter = user_factory()
    code = as_(api, inviter).get("/api/v1/me/referrals").json()["code"]
    api.logout()
    r = api.post("/api/v1/auth/register", {"email": "friend@example.com", "password": "Str0ng-pass-123", "display_name": "Друг",
                                           "accept_terms": True, "ref": code}, format="json")
    assert r.status_code == 201
    stats = as_(api, inviter).get("/api/v1/me/referrals").json()
    assert stats["invited"] == 1 and "Q-10" in stats["reward_policy"]

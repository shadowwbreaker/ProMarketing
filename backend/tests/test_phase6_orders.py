from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from catalog.models import AccountNetwork, NetworkItem
from orders.events import verify_order_chain
from orders.models import Order, OrderItem, OrderTermsVersion, PublicationCheck
from payments.models import FinancialLedgerEntry, Payment, PaymentWebhookEvent, Payout, RefundRequest
from payments.providers.mock import MockPaymentProvider
from payments.providers.registry import set_payment_provider

TERMS = {"brand": "Кофейня «Зерно»", "brief": "Показать напиток, упомянуть акцию", "cta": "Перейди по ссылке в профиле",
         "site_url": "https://example.com"}


@pytest.fixture(autouse=True)
def mock_provider():
    p = MockPaymentProvider()
    set_payment_provider(p)
    yield p
    set_payment_provider(None)


@pytest.fixture
def market(user_factory, account_factory, offer_factory):
    seller = user_factory(roles=("buyer", "seller"))
    buyer = user_factory(roles=("buyer",))
    accs = [account_factory(seller, listed=True) for _ in range(3)]
    offers = [offer_factory(a, price_minor=100_000 * (i + 1)) for i, a in enumerate(accs)]
    return {"seller": seller, "buyer": buyer, "accs": accs, "offers": offers}


def as_(api, user):
    api.force_login(user)
    return api


def create(api, buyer, **body):
    return as_(api, buyer).post("/api/v1/orders", {"terms": TERMS, **body}, format="json")


def pay(api, buyer, order_id, status="succeeded"):
    as_(api, buyer)
    r = api.post(f"/api/v1/orders/{order_id}/pay")
    assert r.status_code == 200, r.content
    pid = r.json()["payment_id"]
    r2 = api.post(f"/api/v1/payments/mock/{pid}/complete", {"status": status}, format="json")
    assert r2.status_code == 200, r2.content
    return pid


def item_url(order_id, item_id, action):
    return f"/api/v1/orders/{order_id}/items/{item_id}/{action}"


def paid_single(api, market, offer_idx=0):
    r = create(api, market["buyer"], offer=str(market["offers"][offer_idx].pk))
    oid = r.json()["id"]
    pay(api, market["buyer"], oid)
    return oid, r.json()["items"][0]["id"]


def to_confirmation(api, market, oid, iid):
    s = as_(api, market["seller"])
    assert s.post(item_url(oid, iid, "accept")).status_code == 200
    r = s.post(item_url(oid, iid, "proof"), {"video_url": "https://www.tiktok.com/@acc1/video/123",
                                             "published_at": timezone.now().isoformat()}, format="json")
    assert r.status_code == 200, r.content
    return r


# --- 6.1 creation --------------------------------------------------------------------
@pytest.mark.django_db
def test_create_order_freezes_price_fee_and_terms(api, market):
    r = create(api, market["buyer"], offer=str(market["offers"][0].pk))
    assert r.status_code == 201, r.content
    o = r.json()
    assert o["status"] == "AWAITING_PAYMENT" and o["total_minor"] == 100_000 and o["fee_bps"] == 500
    it = o["items"][0]
    assert (it["price_minor"], it["fee_minor"], it["seller_amount_minor"]) == (100_000, 5_000, 95_000)
    assert o["terms"]["brand"] == TERMS["brand"] and o["terms"]["version"] == 1 and o["terms"]["placement_days"] == 30
    order = Order.objects.get(pk=o["id"])
    assert hasattr(order, "chat") and verify_order_chain(order)


@pytest.mark.django_db
def test_create_order_rules(api, market, user_factory):
    unverified = user_factory(roles=("buyer",), is_email_verified=False)
    assert create(api, unverified, offer=str(market["offers"][0].pk)).status_code == 403
    assert create(api, market["seller"], offer=str(market["offers"][0].pk)).json()["error"]["code"] == "self_order"
    acc = market["accs"][1]
    acc.is_listed = False
    acc.save()
    assert create(api, market["buyer"], offer=str(market["offers"][1].pk)).json()["error"]["code"] == "offer_unavailable"
    assert create(api, market["buyer"]).status_code == 400


# --- payments (Phase 7 core) ------------------------------------------------------------
@pytest.mark.django_db
def test_payment_only_via_verified_webhook(api, market, mock_provider):
    oid = create(api, market["buyer"], offer=str(market["offers"][0].pk)).json()["id"]
    r1 = api.post(f"/api/v1/orders/{oid}/pay").json()
    r2 = api.post(f"/api/v1/orders/{oid}/pay").json()
    assert r1["payment_id"] == r2["payment_id"]  # repeated click → same payment
    # Returning to the success page does NOT mark the order paid
    assert api.get(f"/api/v1/orders/{oid}").json()["status"] == "AWAITING_PAYMENT"
    payment = Payment.objects.get(pk=r1["payment_id"])
    headers, body = mock_provider.simulate_payment(payment.provider_payment_id)
    bad = api.post("/api/v1/payments/webhooks/mock", data=body, content_type="application/json", HTTP_X_MOCK_SIGNATURE="forged")
    assert bad.status_code == 400 and not PaymentWebhookEvent.objects.exists()
    ok = api.post("/api/v1/payments/webhooks/mock", data=body, content_type="application/json", HTTP_X_MOCK_SIGNATURE=headers["X-Mock-Signature"])
    assert ok.json()["outcome"] == "paid"
    dup = api.post("/api/v1/payments/webhooks/mock", data=body, content_type="application/json", HTTP_X_MOCK_SIGNATURE=headers["X-Mock-Signature"])
    assert dup.json()["outcome"] == "duplicate"
    assert FinancialLedgerEntry.objects.filter(kind="payment_succeeded").count() == 1
    o = api.get(f"/api/v1/orders/{oid}").json()
    assert o["status"] == "AWAITING_SELLER_ACCEPTANCE" and o["paid_at"]
    assert o["items"][0]["accept_deadline"]


@pytest.mark.django_db
def test_webhook_body_is_reconciled_with_provider(api, market, mock_provider):
    """A validly signed but stale 'succeeded' event is ignored if the provider says otherwise."""
    oid = create(api, market["buyer"], offer=str(market["offers"][0].pk)).json()["id"]
    pid = api.post(f"/api/v1/orders/{oid}/pay").json()["payment_id"]
    ppid = Payment.objects.get(pk=pid).provider_payment_id
    headers, body = mock_provider.build_webhook("payment.succeeded", ppid)  # provider state still 'pending'
    r = api.post("/api/v1/payments/webhooks/mock", data=body, content_type="application/json", HTTP_X_MOCK_SIGNATURE=headers["X-Mock-Signature"])
    assert r.json()["outcome"] == "pending"
    assert api.get(f"/api/v1/orders/{oid}").json()["status"] == "AWAITING_PAYMENT"


@pytest.mark.django_db
def test_cancelled_payment_and_unpaid_cancel(api, market):
    oid = create(api, market["buyer"], offer=str(market["offers"][0].pk)).json()["id"]
    pay(api, market["buyer"], oid, status="cancelled")
    assert api.get(f"/api/v1/orders/{oid}").json()["status"] == "AWAITING_PAYMENT"
    assert api.post(f"/api/v1/orders/{oid}/cancel").json()["status"] == "CANCELLED"


# --- 6.2–6.3 lifecycle -------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_full_lifecycle_and_payout_hold(api, market):
    from social_data.core.registry import set_provider_override
    from social_data.providers.fake.provider import FakeProvider

    set_provider_override("tiktok", FakeProvider("tiktok"))
    oid, iid = paid_single(api, market)
    s = as_(api, market["seller"])
    r = s.post(item_url(oid, iid, "accept")).json()
    assert r["items"][0]["status"] == "IN_PROGRESS" and r["items"][0]["publish_deadline"]
    assert r["seller_terms_accepted_at"]
    bad = s.post(item_url(oid, iid, "proof"), {"video_url": "https://evil.example.com/v", "published_at": timezone.now().isoformat()}, format="json")
    assert bad.json()["error"]["code"] == "bad_video_url"
    r = to_confirmation_after_accept(s, oid, iid)
    assert r.json()["items"][0]["status"] == "AWAITING_BUYER_CONFIRMATION"
    assert PublicationCheck.objects.filter(order_item_id=iid, trigger="proof", result="found").exists()
    assert s.post(item_url(oid, iid, "confirm")).status_code == 404  # seller cannot confirm
    b = as_(api, market["buyer"])
    r = b.post(item_url(oid, iid, "confirm")).json()
    assert r["status"] == "COMPLETED"
    po = Payout.objects.get(order_item_id=iid)
    assert po.status == "hold" and po.amount_minor == 95_000
    assert abs((po.available_at - OrderItem.objects.get(pk=iid).confirmed_at) - timedelta(hours=48)) < timedelta(seconds=1)
    assert b.post(item_url(oid, iid, "confirm")).json()["error"]["code"] == "not_awaiting_confirmation"
    set_provider_override("tiktok", None)


def to_confirmation_after_accept(s, oid, iid):
    return s.post(item_url(oid, iid, "proof"), {"video_url": "https://www.tiktok.com/@acc1/video/123",
                                                "published_at": timezone.now().isoformat()}, format="json")


@pytest.mark.django_db
def test_payout_release_withdraw_fail_retry(api, market, mock_provider):
    from payments.services import release_payouts

    oid, iid = paid_single(api, market)
    to_confirmation(api, market, oid, iid)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    po = Payout.objects.get(order_item_id=iid)
    s = as_(api, market["seller"])
    assert s.post(f"/api/v1/me/payouts/{po.pk}/withdraw").json()["error"]["code"] == "payout_not_available"  # still 48h hold
    assert release_payouts(timezone.now() + timedelta(hours=47)) == 0
    assert release_payouts(timezone.now() + timedelta(hours=49)) == 1
    mock_provider.fail_next = "payout"
    assert s.post(f"/api/v1/me/payouts/{po.pk}/withdraw").json()["status"] == "failed"
    r = s.post(f"/api/v1/me/payouts/{po.pk}/retry").json()
    assert r["status"] == "paid"
    assert len(mock_provider.payouts) == 2 and sum(1 for p in mock_provider.payouts.values() if p["status"] == "succeeded") == 1
    assert s.post(f"/api/v1/me/payouts/{po.pk}/withdraw").json()["error"]["code"] == "payout_not_available"  # no double payout
    assert as_(api, market["buyer"]).post(f"/api/v1/me/payouts/{po.pk}/withdraw").status_code == 404


@pytest.mark.django_db
def test_payout_timeout_goes_to_reconciliation(api, market, mock_provider):
    from payments.services import release_payouts

    oid, iid = paid_single(api, market)
    to_confirmation(api, market, oid, iid)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    release_payouts(timezone.now() + timedelta(hours=49))
    po = Payout.objects.get(order_item_id=iid)
    mock_provider.fail_next = "timeout_payout"
    assert as_(api, market["seller"]).post(f"/api/v1/me/payouts/{po.pk}/withdraw").json()["status"] == "pending_reconciliation"


@pytest.mark.django_db
def test_price_change_after_payment_does_not_affect_order(api, market):
    oid, iid = paid_single(api, market)
    as_(api, market["seller"]).patch(f"/api/v1/offers/{market['offers'][0].pk}", {"price_minor": 999_999}, format="json")
    assert as_(api, market["buyer"]).get(f"/api/v1/orders/{oid}").json()["items"][0]["price_minor"] == 100_000


# --- 6.5 networks --------------------------------------------------------------------------
def make_network(market, total=None, partial=True):
    net = AccountNetwork.objects.create(owner=market["seller"], title="Сетка", total_price_minor=total, allow_partial_purchase=partial)
    items = [NetworkItem.objects.create(network=net, social_account=a, offer=o, price_minor=o.price_minor)
             for a, o in zip(market["accs"], market["offers"], strict=True)]
    return net, items


@pytest.mark.django_db
def test_network_order_whole_and_partial(api, market):
    net, items = make_network(market, total=500_001)
    o = create(api, market["buyer"], network=str(net.pk)).json()
    prices = [i["price_minor"] for i in o["items"]]
    assert sum(prices) == 500_001 == o["total_minor"] and len(prices) == 3
    assert prices == sorted(prices)  # proportional to 100k/200k/300k
    o2 = create(api, market["buyer"], network=str(net.pk), network_items=[str(items[2].pk)]).json()
    assert o2["total_minor"] == 300_000 and len(o2["items"]) == 1
    net.allow_partial_purchase = False
    net.save()
    r = create(api, market["buyer"], network=str(net.pk), network_items=[str(items[0].pk)])
    assert r.json()["error"]["code"] == "partial_not_allowed"


@pytest.mark.django_db
def test_partial_network_fulfilment_refunds_only_failed_item(api, market):
    from orders.services import expire_unaccepted

    net, _ = make_network(market)
    o = create(api, market["buyer"], network=str(net.pk)).json()
    oid = o["id"]
    ids = [i["id"] for i in o["items"]]
    pay(api, market["buyer"], oid)
    s = as_(api, market["seller"])
    for iid in ids[:2]:
        s.post(item_url(oid, iid, "accept"))
        to_confirmation_after_accept(s, oid, iid)
    expire_unaccepted(timezone.now() + timedelta(hours=25))  # third account never accepted
    b = as_(api, market["buyer"])
    for iid in ids[:2]:
        b.post(item_url(oid, iid, "confirm"))
    o = b.get(f"/api/v1/orders/{oid}").json()
    statuses = {i["id"]: i["status"] for i in o["items"]}
    assert statuses[ids[0]] == statuses[ids[1]] == "COMPLETED" and statuses[ids[2]] == "REFUNDED"
    assert o["status"] == "PARTIALLY_REFUNDED"
    assert list(RefundRequest.objects.values_list("order_item_id", "amount_minor", "status")) == [
        (OrderItem.objects.get(pk=ids[2]).pk, 300_000, "succeeded")]
    assert Payout.objects.filter(order_item_id__in=ids[:2]).count() == 2


# --- refunds -------------------------------------------------------------------------------
@pytest.mark.django_db
def test_no_double_refund_and_partial_refunds(api, market, mock_provider):
    from common.exceptions import DomainError
    from payments.services import refund_item

    oid, iid = paid_single(api, market, offer_idx=1)  # 200 000
    refund_item(iid, amount_minor=50_000, reason="частично", actor=market["buyer"])
    assert OrderItem.objects.get(pk=iid).status == "PARTIALLY_REFUNDED"
    with pytest.raises(DomainError) as e:
        refund_item(iid, amount_minor=150_001, reason="x", actor=None)
    assert e.value.code == "refund_exceeds_paid"
    refund_item(iid, amount_minor=None, reason="остаток", actor=None)
    assert OrderItem.objects.get(pk=iid).status == "REFUNDED"
    with pytest.raises(DomainError):
        refund_item(iid, amount_minor=None, reason="ещё раз", actor=None)
    payment = Payment.objects.get(order_id=oid)
    assert mock_provider.payments[payment.provider_payment_id]["refunded"] == 200_000


@pytest.mark.django_db
def test_refund_timeout_and_after_payout(api, market, mock_provider):
    from common.exceptions import DomainError
    from payments.services import refund_item, release_payouts, withdraw

    oid, iid = paid_single(api, market)
    mock_provider.fail_next = "timeout_refund"
    r = refund_item(iid, amount_minor=10_000, reason="x", actor=None)
    assert r.status == "pending_reconciliation"
    with pytest.raises(DomainError):  # pending amount counts towards the limit
        refund_item(iid, amount_minor=95_000, reason="y", actor=None)
    oid2, iid2 = paid_single(api, market, offer_idx=2)
    to_confirmation(api, market, oid2, iid2)
    as_(api, market["buyer"]).post(item_url(oid2, iid2, "confirm"))
    release_payouts(timezone.now() + timedelta(hours=49))
    withdraw(Payout.objects.get(order_item_id=iid2).pk, actor=market["seller"])
    with pytest.raises(DomainError) as e:
        refund_item(iid2, amount_minor=None, reason="поздно", actor=None)
    assert e.value.code == "payout_already_made"  # R-01


@pytest.mark.django_db
def test_partial_refund_reduces_payout_with_fee(api, market):
    from payments.services import refund_item

    oid, iid = paid_single(api, market)  # 100 000
    to_confirmation(api, market, oid, iid)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    refund_item(iid, amount_minor=40_000, reason="частично", actor=None)
    assert Payout.objects.get(order_item_id=iid).amount_minor == 60_000 - 3_000


# --- buyer/seller cancellations & timers ---------------------------------------------------
@pytest.mark.django_db
def test_cancel_before_acceptance_and_decline(api, market):
    oid, iid = paid_single(api, market)
    r = as_(api, market["buyer"]).post(item_url(oid, iid, "cancel")).json()
    assert r["items"][0]["status"] == "REFUNDED"
    oid2, iid2 = paid_single(api, market, offer_idx=1)
    s = as_(api, market["seller"])
    assert s.post(item_url(oid2, iid2, "decline"), {"reason": ""}, format="json").json()["error"]["code"] == "reason_required"
    assert s.post(item_url(oid2, iid2, "decline"), {"reason": "не моя тема"}, format="json").json()["items"][0]["status"] == "REFUNDED"
    oid3, iid3 = paid_single(api, market, offer_idx=2)
    assert as_(api, market["seller"]).post(item_url(oid3, iid3, "accept")).status_code == 200
    assert as_(api, market["buyer"]).post(item_url(oid3, iid3, "cancel")).json()["error"]["code"] == "already_accepted"


@pytest.mark.django_db
def test_seller_cannot_accept_after_deadline(api, market):
    oid, iid = paid_single(api, market)
    with freeze_time(timezone.now() + timedelta(hours=25)):
        assert as_(api, market["seller"]).post(item_url(oid, iid, "accept")).json()["error"]["code"] == "accept_deadline_passed"


@pytest.mark.django_db(transaction=True)
def test_confirmation_window_auto_confirm_or_ticket(api, market):
    from orders.services import process_confirmation_windows
    from social_data.core.registry import set_provider_override
    from social_data.providers.fake.provider import FakeProvider
    from support.models import SupportTicket

    set_provider_override("tiktok", FakeProvider("tiktok"))
    oid, iid = paid_single(api, market)
    to_confirmation(api, market, oid, iid)
    oid2, iid2 = paid_single(api, market, offer_idx=1)
    s = as_(api, market["seller"])
    s.post(item_url(oid2, iid2, "accept"))
    s.post(item_url(oid2, iid2, "proof"), {"video_url": "https://www.tiktok.com/@acc2/video/deleted",
                                           "published_at": timezone.now().isoformat()}, format="json")
    assert process_confirmation_windows(timezone.now() + timedelta(hours=73)) == 2
    assert OrderItem.objects.get(pk=iid).status == "COMPLETED"  # video found → auto-confirmed
    assert OrderItem.objects.get(pk=iid2).status == "AWAITING_BUYER_CONFIRMATION"  # not found → staff review
    assert SupportTicket.objects.filter(order_id=oid2, category="auto_confirm_check").exists()
    set_provider_override("tiktok", None)


@pytest.mark.django_db(transaction=True)
def test_buyer_publication_checks_limited(api, market, settings):
    from social_data.core.registry import set_provider_override
    from social_data.providers.fake.provider import FakeProvider

    set_provider_override("tiktok", FakeProvider("tiktok"))
    settings.BUYER_PUBLICATION_CHECKS_LIMIT = 2
    oid, iid = paid_single(api, market)
    b = as_(api, market["buyer"])
    assert b.post(item_url(oid, iid, "check-publication")).json()["error"]["code"] == "no_proof"
    to_confirmation(api, market, oid, iid)
    b = as_(api, market["buyer"])
    assert b.post(item_url(oid, iid, "check-publication")).status_code == 200
    assert b.post(item_url(oid, iid, "check-publication")).status_code == 200
    assert b.post(item_url(oid, iid, "check-publication")).status_code == 429
    set_provider_override("tiktok", None)


@pytest.mark.django_db
def test_missed_deadline_notifies_without_refund(api, market):
    from notifications.models import Notification
    from orders.services import notify_missed_publish_deadlines

    oid, iid = paid_single(api, market)
    as_(api, market["seller"]).post(item_url(oid, iid, "accept"))
    later = timezone.now() + timedelta(days=8)
    assert notify_missed_publish_deadlines(later) == 1
    assert notify_missed_publish_deadlines(later) == 0  # once
    assert OrderItem.objects.get(pk=iid).status == "IN_PROGRESS"
    assert Notification.objects.filter(user=market["buyer"], type="order.deadline_missed").exists()


# --- terms (scenario 11) and materials (scenario 14) ---------------------------------------
@pytest.mark.django_db
def test_terms_change_requires_other_party(api, market):
    oid, iid = paid_single(api, market)
    b = as_(api, market["buyer"])
    assert b.post(f"/api/v1/orders/{oid}/terms/propose", {"changes": {"brand": "Другое"}}, format="json").json()["error"]["code"] == "bad_terms_fields"
    o = b.post(f"/api/v1/orders/{oid}/terms/propose", {"changes": {"brief": "Новое ТЗ"}, "comment": "уточнение"}, format="json").json()
    pid = o["proposals"][0]["id"]
    assert o["terms"]["brief"] == TERMS["brief"]  # not binding automatically
    assert b.post(f"/api/v1/orders/{oid}/terms/{pid}/decide", {"accept": True}, format="json").status_code == 403
    o = as_(api, market["seller"]).post(f"/api/v1/orders/{oid}/terms/{pid}/decide", {"accept": True}, format="json").json()
    assert o["terms"]["brief"] == "Новое ТЗ" and o["terms"]["version"] == 2
    v1 = OrderTermsVersion.objects.get(order_id=oid, version=1)
    assert v1.brief == TERMS["brief"]
    with pytest.raises(PermissionError):
        v1.brief = "tamper"
        v1.save()


@pytest.mark.django_db
def test_materials_delay_extends_deadline(api, market):
    md = timezone.now() + timedelta(days=1)
    r = as_(api, market["buyer"]).post("/api/v1/orders", {"offer": str(market["offers"][0].pk),
                                                          "terms": {**TERMS, "materials_deadline": md.isoformat()}}, format="json")
    oid, iid = r.json()["id"], r.json()["items"][0]["id"]
    pay(api, market["buyer"], oid)
    before = as_(api, market["seller"]).post(item_url(oid, iid, "accept")).json()["items"][0]["publish_deadline"]
    with freeze_time(md + timedelta(days=2)):
        as_(api, market["buyer"]).post(f"/api/v1/orders/{oid}/materials-delivered")
    item = OrderItem.objects.get(pk=iid)
    from django.utils.dateparse import parse_datetime

    assert (item.publish_deadline - parse_datetime(before)).days == 2


# --- access & history -------------------------------------------------------------------------
@pytest.mark.django_db
def test_order_access_and_history(api, market, user_factory):
    oid, iid = paid_single(api, market)
    stranger = user_factory()
    assert as_(api, stranger).get(f"/api/v1/orders/{oid}").status_code == 404
    assert api.post(item_url(oid, iid, "accept")).status_code == 404
    support = user_factory(roles=("support_agent",))
    assert as_(api, support).get(f"/api/v1/orders/{oid}").json()["role"] == "staff"
    events = as_(api, market["buyer"]).get(f"/api/v1/orders/{oid}/events").json()
    assert [e["type"] for e in events][:3] == ["order.created", "item.submitted", "payment.started"]
    assert verify_order_chain(Order.objects.get(pk=oid))
    assert as_(api, market["buyer"]).get("/api/v1/me/purchases").json()["count"] == 1


@pytest.mark.django_db
def test_mock_complete_accepts_provider_id_and_is_owner_only(api, market, user_factory, settings):
    oid = create(api, market["buyer"], offer=str(market["offers"][0].pk)).json()["id"]
    pid = api.post(f"/api/v1/orders/{oid}/pay").json()["payment_id"]
    ppid = Payment.objects.get(pk=pid).provider_payment_id
    assert as_(api, user_factory()).post(f"/api/v1/payments/mock/{ppid}/complete").status_code == 404
    assert as_(api, market["buyer"]).post(f"/api/v1/payments/mock/{ppid}/complete").json()["outcome"] == "paid"
    settings.PAYMENT_PROVIDER = "yookassa"
    assert api.post(f"/api/v1/payments/mock/{ppid}/complete").status_code == 404  # dev-only endpoint

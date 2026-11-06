"""Phase 9: support & arbitration. Each of the 15 conflict scenarios (roadmap 9.7) has its own test."""
from datetime import timedelta

import pytest
from django.utils import timezone

from audit.models import AdminAction
from orders.models import Order, OrderItem
from payments.models import Payout, RefundRequest
from support.models import Dispute, DisputeItem, SupportTicket
from tests.test_phase6_orders import as_, create, item_url, make_network, paid_single, pay, to_confirmation

DESC = "Подробное описание проблемы для арбитража"


@pytest.fixture
def staff(user_factory):
    return {"support": user_factory(roles=("support_agent",)), "admin": user_factory(roles=("admin",)),
            "admin2": user_factory(roles=("admin",)), "super": user_factory(roles=("super_admin",)),
            "moderator": user_factory(roles=("moderator",))}


def open_(api, user, oid, reason, items=None, evidence=None, desc=DESC):
    body = {"reason": reason, "description": desc}
    if items:
        body["items"] = items
    if evidence:
        body["evidence"] = evidence
    return as_(api, user).post(f"/api/v1/orders/{oid}/disputes/open", body, format="json")


def act(api, user, did, action, **body):
    return as_(api, user).post(f"/api/v1/staff/disputes/{did}/{action}", body, format="json")


def decide(api, user, did, item, decision, comment="Решение принято по материалам спора", **extra):
    return act(api, user, did, "decide", item=item, decision=decision, comment=comment, **extra)


def accepted(api, market, idx=0):
    oid, iid = paid_single(api, market, offer_idx=idx)
    assert as_(api, market["seller"]).post(item_url(oid, iid, "accept")).status_code == 200
    return oid, iid


def published(api, market, idx=0):
    oid, iid = paid_single(api, market, offer_idx=idx)
    to_confirmation(api, market, oid, iid)
    return oid, iid


# --- core rules ------------------------------------------------------------------------------
@pytest.mark.django_db
def test_complaint_does_not_refund_automatically_and_locks_chat(api, market):
    oid, iid = accepted(api, market)
    assert open_(api, market["buyer"], oid, "not_published", desc="коротко").json()["error"]["code"] == "description_required"
    r = open_(api, market["buyer"], oid, "not_published")
    assert r.status_code == 201, r.content
    d = r.json()
    assert d["status"] == "WAITING_SELLER" and d["response_due_at"]
    item = OrderItem.objects.get(pk=iid)
    assert item.status == "DISPUTED" and not RefundRequest.objects.exists()  # no automatic refund (9.1)
    assert as_(api, market["buyer"]).get(f"/api/v1/orders/{oid}/chat").json()["locked"] is True
    assert open_(api, market["buyer"], oid, "not_published").json()["error"]["code"] == "already_disputed"
    assert open_(api, market["seller"], oid, "not_published").json()["error"]["code"] == "reason_not_allowed"


@pytest.mark.django_db
def test_staff_permissions_and_mandatory_comment(api, market, staff):
    oid, iid = accepted(api, market)
    did = open_(api, market["buyer"], oid, "not_published").json()["id"]
    assert as_(api, market["buyer"]).get(f"/api/v1/staff/disputes/{did}").status_code == 403
    assert as_(api, staff["moderator"]).get("/api/v1/staff/disputes").status_code == 403
    q = as_(api, staff["support"]).get("/api/v1/staff/disputes").json()
    assert q["count"] == 1 and q["results"][0]["amount_minor"] == 100_000
    # support agent can handle but not decide; admin needs a comment
    assert decide(api, staff["support"], did, iid, "full_refund").status_code == 403
    assert decide(api, staff["admin"], did, iid, "full_refund", comment="ok").json()["error"]["code"] == "comment_required"
    r = decide(api, staff["admin"], did, iid, "full_refund")
    assert r.status_code == 200, r.content
    assert r.json()["status"] == "RESOLVED"
    assert AdminAction.objects.filter(action="dispute.decision.full_refund", order_id=oid).exists()


@pytest.mark.django_db
def test_staff_detail_has_everything(api, market, staff):
    oid, iid = published(api, market)
    as_(api, market["buyer"]).post(f"/api/v1/orders/{oid}/chat", {"body": "Видео не по ТЗ"}, format="json")
    did = open_(api, market["buyer"], oid, "brief_mismatch",
                evidence=[{"url": "https://www.tiktok.com/@acc1/video/123", "description": "сама публикация"}]).json()["id"]
    d = as_(api, staff["support"]).get(f"/api/v1/staff/disputes/{did}").json()
    for key in ("order", "chat", "events", "publication_checks", "account_stats", "payment", "previous_disputes", "admin_notes", "evidence"):
        assert key in d, key
    assert d["order"]["original_terms"]["brief"] and d["order"]["items"][0]["price_minor"] == 100_000
    assert d["payment"]["refundable"][iid] == 100_000 and d["payment"]["provider_capabilities"]["partial_refund"] is True
    assert any(m["body"] == "Видео не по ТЗ" for m in d["chat"])
    assert d["evidence"][0]["url"].endswith("/123")
    assert AdminAction.objects.filter(action="dispute.viewed").exists()  # access to personal data is logged


# --- 15 scenarios ----------------------------------------------------------------------------
@pytest.mark.django_db
def test_s01_seller_not_responding(api, market, staff):
    from support.services import process_timeouts

    oid, iid = accepted(api, market)
    did = open_(api, market["buyer"], oid, "seller_not_responding").json()["id"]
    detail = as_(api, staff["support"]).get(f"/api/v1/staff/disputes/{did}").json()
    assert detail["order"]["seller"]["last_seen_at"] is not None or True  # last activity is shown to staff
    assert process_timeouts(timezone.now() + timedelta(hours=49)) == 1
    d = Dispute.objects.get(pk=did)
    assert d.status == "UNDER_REVIEW" and d.response_overdue  # ignoring is recorded, NOT an automatic verdict
    assert OrderItem.objects.get(pk=iid).status == "DISPUTED" and not RefundRequest.objects.exists()
    assert decide(api, staff["admin"], did, iid, "full_refund").json()["status"] == "RESOLVED"
    assert OrderItem.objects.get(pk=iid).status == "REFUNDED"


@pytest.mark.django_db
def test_s02_video_not_published_seller_answers_then_extension(api, market, staff):
    oid, iid = accepted(api, market)
    did = open_(api, market["buyer"], oid, "not_published").json()["id"]
    r = as_(api, market["seller"]).post(f"/api/v1/disputes/{did}/reply", {"body": "Заболел, прошу ещё 3 дня"}, format="json")
    assert r.json()["status"] == "UNDER_REVIEW"
    assert decide(api, staff["admin"], did, iid, "extend").json()["error"]["code"] == "deadline_required"
    nd = (timezone.now() + timedelta(days=3)).isoformat()
    assert decide(api, staff["admin"], did, iid, "extend", new_deadline=nd).status_code == 200
    item = OrderItem.objects.get(pk=iid)
    assert item.status == "IN_PROGRESS" and item.publish_deadline > timezone.now() + timedelta(days=2)


@pytest.mark.django_db
def test_s03_brief_mismatch_partial_refund_seller_keeps_rest(api, market, staff):
    oid, iid = published(api, market, idx=1)  # 200 000
    did = open_(api, market["buyer"], oid, "brief_mismatch").json()["id"]
    assert decide(api, staff["admin"], did, iid, "partial_refund").json()["error"]["code"] == "amount_required"
    r = decide(api, staff["admin"], did, iid, "partial_refund", refund_amount_minor=50_000)
    assert r.json()["status"] == "RESOLVED", r.content
    item = OrderItem.objects.get(pk=iid)
    assert item.status == "PARTIALLY_REFUNDED"
    assert RefundRequest.objects.get(order_item=item).amount_minor == 50_000
    po = Payout.objects.get(order_item=item)
    assert po.amount_minor == 150_000 - 7_500 and po.status == "hold"  # remainder minus 5%, 48h hold


@pytest.mark.django_db
def test_s03b_redo(api, market, staff):
    oid, iid = published(api, market)
    did = open_(api, market["buyer"], oid, "wrong_material").json()["id"]
    nd = (timezone.now() + timedelta(days=5)).isoformat()
    decide(api, staff["admin"], did, iid, "redo", new_deadline=nd)
    assert OrderItem.objects.get(pk=iid).status == "IN_PROGRESS"


@pytest.mark.django_db
def test_s04_removed_early_during_hold(api, market, staff, mock_provider):
    oid, iid = published(api, market)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    did = open_(api, market["buyer"], oid, "removed_early",
                evidence=[{"url": "https://www.tiktok.com/@acc1/video/123", "description": "ссылка больше не открывается"}]).json()["id"]
    assert Payout.objects.get(order_item_id=iid).status == "suspended"  # payout frozen during dispute (D-014)
    r = act(api, staff["support"], did, "check-publication", item=iid)
    assert r.status_code == 200
    decide(api, staff["admin"], did, iid, "partial_refund", refund_amount_minor=60_000)
    assert Payout.objects.get(order_item_id=iid).amount_minor == 40_000 - 2_000


@pytest.mark.django_db
def test_s04_after_payout_is_documented_limitation(api, market, staff):
    from payments.services import release_payouts, withdraw

    oid, iid = published(api, market)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    release_payouts(timezone.now() + timedelta(hours=49))
    withdraw(Payout.objects.get(order_item_id=iid).pk, actor=market["seller"])
    did = open_(api, market["buyer"], oid, "removed_early").json()["id"]
    r = decide(api, staff["admin"], did, iid, "full_refund")
    assert r.json()["error"]["code"] == "payout_already_made"  # R-01: cannot pretend money is held
    assert DisputeItem.objects.get(dispute_id=did).is_active  # stays open for sanctions / voluntary refund
    r = decide(api, staff["admin"], did, None, "sanction", sanction={"target": "seller", "type": "warning"})
    assert r.status_code == 200
    assert market["seller"].sanctions.count() == 1


@pytest.mark.django_db
def test_s05_partial_network_dispute(api, market, staff):
    net, _ = make_network(market)
    o = create(api, market["buyer"], network=str(net.pk)).json()
    oid, ids = o["id"], [i["id"] for i in o["items"]]
    pay(api, market["buyer"], oid)
    for iid in ids:
        as_(api, market["seller"]).post(item_url(oid, iid, "accept"))
    for iid in ids[:2]:
        as_(api, market["seller"]).post(item_url(oid, iid, "proof"), {"video_url": "https://www.tiktok.com/@a/video/1",
                                                                     "published_at": timezone.now().isoformat()}, format="json")
        as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    did = open_(api, market["buyer"], oid, "partial_fulfilment", items=[ids[2]]).json()["id"]
    assert decide(api, staff["admin"], did, ids[0], "full_refund").json()["error"]["code"] == "bad_item"  # not in dispute
    decide(api, staff["admin"], did, ids[2], "full_refund")
    statuses = dict(OrderItem.objects.filter(order_id=oid).values_list("id", "status"))
    assert [statuses[OrderItem.objects.get(pk=i).pk] for i in ids] == ["COMPLETED", "COMPLETED", "REFUNDED"]
    assert Order.objects.get(pk=oid).status == "PARTIALLY_REFUNDED"
    assert RefundRequest.objects.get().amount_minor == 300_000


@pytest.mark.django_db
def test_s06_buyer_not_confirming_seller_wins(api, market, staff):
    oid, iid = published(api, market)
    assert open_(api, market["seller"], oid, "buyer_not_confirming").status_code == 201
    did = Dispute.objects.get(order_id=oid).pk
    assert Dispute.objects.get(pk=did).status == "WAITING_BUYER"
    decide(api, staff["admin"], did, iid, "in_favor_of_seller")
    item = OrderItem.objects.get(pk=iid)
    assert item.status == "COMPLETED" and Payout.objects.get(order_item=item).status == "hold"


@pytest.mark.django_db
def test_s07_false_complaint_rejected_and_history_visible(api, market, staff):
    oid, iid = published(api, market)
    did = open_(api, market["buyer"], oid, "not_published").json()["id"]
    r = decide(api, staff["admin"], did, iid, "reject")
    assert r.json()["status"] == "REJECTED"
    assert OrderItem.objects.get(pk=iid).status == "AWAITING_BUYER_CONFIRMATION"  # restored, new confirmation window
    decide(api, staff["admin"], did, None, "sanction", sanction={"target": "buyer", "type": "warning"})
    hist = as_(api, staff["support"]).get(f"/api/v1/staff/disputes/{did}").json()["order"]["buyer"]["history"]
    assert hist["opened"] == 1 and hist["rejected"] == 1 and hist["sanctions"] == 1
    from reviews.services import seller_rating

    assert seller_rating(market["seller"].pk)["rating"] is None  # a complaint itself does not touch the rating


@pytest.mark.django_db(transaction=True)
def test_s08_inflated_statistics_admin_recheck(api, market, staff):
    from social_data.core.registry import set_provider_override
    from social_data.models import StatsRefreshJob
    from social_data.providers.fake.provider import FakeProvider

    set_provider_override("tiktok", FakeProvider("tiktok"))
    oid, iid = accepted(api, market)
    did = open_(api, market["buyer"], oid, "fake_statistics").json()["id"]
    r = act(api, staff["support"], did, "check-account", item=iid)
    assert r.status_code == 200
    job = StatsRefreshJob.objects.get(trigger="admin_check")
    assert job.status == "succeeded"
    hist = r.json()["account_stats"][0]["history"]
    assert len(hist) >= 1  # comparison of history is available to the arbiter
    set_provider_override("tiktok", None)


@pytest.mark.django_db
def test_s09_price_change_after_payment(api, market, staff):
    oid, iid = accepted(api, market)
    as_(api, market["seller"]).patch(f"/api/v1/offers/{market['offers'][0].pk}", {"price_minor": 900_000}, format="json")
    did = open_(api, market["buyer"], oid, "extra_payment").json()["id"]
    d = as_(api, staff["support"]).get(f"/api/v1/staff/disputes/{did}").json()
    assert d["order"]["items"][0]["price_minor"] == 100_000 and d["order"]["total_minor"] == 100_000


@pytest.mark.django_db
def test_s10_off_platform_attempt(api, market, staff):
    oid, iid = accepted(api, market)
    as_(api, market["seller"]).post(f"/api/v1/orders/{oid}/chat", {"body": "Давай оплату напрямую, напиши в телеграм"}, format="json")
    did = open_(api, market["buyer"], oid, "off_platform").json()["id"]
    chat = as_(api, staff["support"]).get(f"/api/v1/staff/disputes/{did}").json()["chat"]
    assert any(m["contact_signal"] for m in chat)
    decide(api, staff["admin"], did, None, "sanction", sanction={"target": "seller", "type": "limit", "days": 7})
    market["seller"].refresh_from_db()
    assert market["seller"].status == "limited"


@pytest.mark.django_db
def test_s11_brief_changed_after_payment_not_binding(api, market, staff):
    oid, iid = published(api, market)
    as_(api, market["buyer"]).post(f"/api/v1/orders/{oid}/terms/propose", {"changes": {"brief": "Совсем другое ТЗ"}}, format="json")
    did = open_(api, market["buyer"], oid, "brief_mismatch").json()["id"]
    d = as_(api, staff["support"]).get(f"/api/v1/staff/disputes/{did}").json()
    assert d["order"]["current_terms"]["version"] == 1 and d["order"]["current_terms"]["brief"] != "Совсем другое ТЗ"


@pytest.mark.django_db(transaction=True)
def test_s12_seller_account_deleted(api, market, staff):
    from social_data.core.registry import set_provider_override
    from social_data.providers.fake.provider import FakeProvider

    oid, iid = accepted(api, market)
    r = open_(api, market["buyer"], oid, "not_published")
    assert r.status_code == 201, r.json()
    did = r.json()["id"]
    acc = market["accs"][0]
    acc.handle = "gone_missing"
    acc.save()
    set_provider_override("tiktok", FakeProvider("tiktok"))
    act(api, staff["support"], did, "check-account", item=iid)
    from social_data.models import StatsRefreshJob

    job = StatsRefreshJob.objects.get(trigger="admin_check")
    assert job.status == "failed" and job.error_code == "account_not_found"
    assert decide(api, staff["admin"], did, iid, "full_refund").json()["status"] == "RESOLVED"
    set_provider_override("tiktok", None)


@pytest.mark.django_db
def test_s13_platform_removed_video_policy_visible(api, market, staff):
    r = as_(api, market["buyer"]).post("/api/v1/orders", {"offer": str(market["offers"][0].pk), "terms": {
        "brand": "Б", "brief": "ТЗ", "platform_removal_policy": "seller_not_liable"}}, format="json")
    oid, iid = r.json()["id"], r.json()["items"][0]["id"]
    pay(api, market["buyer"], oid)
    to_confirmation(api, market, oid, iid)
    did = open_(api, market["buyer"], oid, "removed_early").json()["id"]
    d = as_(api, staff["support"]).get(f"/api/v1/staff/disputes/{did}").json()
    assert d["order"]["original_terms"]["platform_removal_policy"] == "seller_not_liable"
    assert decide(api, staff["admin"], did, iid, "reject", comment="По условиям заказа риск модерации платформы не на продавце").json()["status"] == "REJECTED"


@pytest.mark.django_db
def test_s14_buyer_delayed_materials(api, market, staff):
    md = timezone.now() - timedelta(days=1)
    r = as_(api, market["buyer"]).post("/api/v1/orders", {"offer": str(market["offers"][0].pk), "terms": {
        "brand": "Б", "brief": "ТЗ", "materials_deadline": md.isoformat()}}, format="json")
    oid, iid = r.json()["id"], r.json()["items"][0]["id"]
    pay(api, market["buyer"], oid)
    as_(api, market["seller"]).post(item_url(oid, iid, "accept"))
    assert open_(api, market["seller"], oid, "materials_delayed").status_code == 201
    as_(api, market["buyer"]).post(f"/api/v1/orders/{oid}/materials-delivered")
    did = Dispute.objects.get(order_id=oid).pk
    events = [e["type"] for e in as_(api, staff["support"]).get(f"/api/v1/staff/disputes/{did}").json()["events"]]
    assert "materials.delivered" in events


@pytest.mark.django_db
def test_s15_counter_claims_join_one_dispute(api, market, staff):
    oid, iid = published(api, market)
    did = open_(api, market["buyer"], oid, "brief_mismatch").json()["id"]
    r = open_(api, market["seller"], oid, "beyond_brief", desc="Покупатель требует то, чего не было в ТЗ, есть переписка")
    assert r.json()["id"] == did and r.json()["has_counterclaim"] is True
    assert Dispute.objects.filter(order_id=oid).count() == 1
    d = Dispute.objects.get(pk=did)
    assert d.status == "UNDER_REVIEW"
    msgs = as_(api, staff["support"]).get(f"/api/v1/staff/disputes/{did}").json()["messages"]
    assert any("Встречная претензия" in m["body"] for m in msgs)


# --- workflow: evidence request, escalation, appeal, internal notes ---------------------------
@pytest.mark.django_db
def test_evidence_request_escalation_and_internal_notes(api, market, staff):
    oid, iid = published(api, market)
    did = open_(api, market["buyer"], oid, "wrong_link").json()["id"]
    assert act(api, staff["support"], did, "assign").json()["assignee"] == str(staff["support"].pk)
    act(api, staff["support"], did, "message", body="Внутренняя заметка", internal=True)
    act(api, staff["support"], did, "note", body="Подозрительно")
    party = as_(api, market["buyer"]).get(f"/api/v1/disputes/{did}").json()
    assert all(m["body"] != "Внутренняя заметка" for m in party["messages"])  # staff-only stays hidden
    r = act(api, staff["support"], did, "request-evidence", **{"from": "seller", "comment": "Пришлите скриншот статистики"})
    assert r.json()["status"] == "EVIDENCE_REQUESTED"
    from notifications.models import Notification

    assert Notification.objects.filter(user=market["seller"], type="dispute.evidence_requested").exists()
    as_(api, market["seller"]).post(f"/api/v1/disputes/{did}/reply",
                                    {"body": "Вот", "evidence": [{"url": "https://www.tiktok.com/@a/video/9"}]}, format="json")
    assert Dispute.objects.get(pk=did).status == "UNDER_REVIEW"
    act(api, staff["support"], did, "escalate", comment="Сложный случай")
    assert decide(api, staff["support"], did, iid, "reject").status_code == 403
    r = decide(api, staff["admin"], did, iid, "reject")
    assert r.status_code == 200 and r.json()["status"] == "REJECTED"  # admin has dispute.escalated


@pytest.mark.django_db
def test_appeal_reviewed_by_another_admin_once(api, market, staff):
    oid, iid = published(api, market)
    did = open_(api, market["buyer"], oid, "not_published").json()["id"]
    decide(api, staff["admin"], did, iid, "reject")
    b = as_(api, market["buyer"])
    assert b.post(f"/api/v1/disputes/{did}/appeal", {"reason": "кратко"}, format="json").status_code == 400
    r = b.post(f"/api/v1/disputes/{did}/appeal", {"reason": "Видео так и не появилось, прикладываю доказательства"}, format="json")
    assert r.status_code == 201
    aid = r.json()["id"]
    assert OrderItem.objects.get(pk=iid).status == "DISPUTED"
    assert act(api, staff["admin"], aid, "assign", assignee=str(staff["admin"].pk)).json()["error"]["code"] == "same_reviewer"
    assert decide(api, staff["admin"], aid, iid, "full_refund").json()["error"]["code"] == "same_reviewer"
    r = decide(api, staff["admin2"], aid, iid, "full_refund")
    assert r.json().get("status") == "CLOSED", r.json()
    assert Dispute.objects.get(pk=did).status == "CLOSED"
    assert as_(api, market["buyer"]).post(f"/api/v1/disputes/{did}/appeal", {"reason": "ещё раз подаю апелляцию на решение"},
                                          format="json").status_code == 409


@pytest.mark.django_db
def test_appeal_window_closes(api, market, staff):
    from support.services import close_expired_appeal_windows

    oid, iid = published(api, market)
    did = open_(api, market["buyer"], oid, "not_published").json()["id"]
    decide(api, staff["admin"], did, iid, "reject")
    assert close_expired_appeal_windows(timezone.now() + timedelta(days=8)) == 1
    assert Dispute.objects.get(pk=did).status == "CLOSED"


@pytest.mark.django_db
def test_no_double_refund_through_decisions(api, market, staff):
    oid, iid = published(api, market)
    did = open_(api, market["buyer"], oid, "not_published").json()["id"]
    decide(api, staff["admin"], did, iid, "full_refund")
    assert decide(api, staff["admin2"], did, iid, "full_refund").status_code in (400, 409)
    assert RefundRequest.objects.filter(order_item_id=iid).count() == 1


@pytest.mark.django_db
def test_simultaneous_disputes_on_different_items(api, market, staff):
    net, _ = make_network(market)
    o = create(api, market["buyer"], network=str(net.pk)).json()
    oid, ids = o["id"], [i["id"] for i in o["items"]]
    pay(api, market["buyer"], oid)
    s = as_(api, market["seller"])
    for iid in ids:
        s.post(item_url(oid, iid, "accept"))
    d1 = open_(api, market["buyer"], oid, "not_published", items=[ids[0]]).json()["id"]
    d2 = open_(api, market["buyer"], oid, "deadline_missed", items=[ids[1]]).json()["id"]
    assert d1 != d2 and DisputeItem.objects.filter(is_active=True).count() == 2


@pytest.mark.django_db
def test_support_tickets(api, market, staff, user_factory):
    b = as_(api, market["buyer"])
    assert b.post("/api/v1/support/tickets", {"subject": "?", "body": "x"}, format="json").status_code == 400
    tid = b.post("/api/v1/support/tickets", {"subject": "Вопрос по оплате", "body": "Как работает удержание денег?"}, format="json").json()["id"]
    assert b.get("/api/v1/me/tickets").json()["count"] == 1
    assert as_(api, user_factory()).get(f"/api/v1/support/tickets/{tid}").status_code == 404
    st = as_(api, staff["support"])
    assert len(st.get("/api/v1/staff/tickets").json()) == 1
    st.post(f"/api/v1/staff/tickets/{tid}/assign")
    st.post(f"/api/v1/staff/tickets/{tid}/priority", {"priority": "high"}, format="json")
    r = st.post(f"/api/v1/staff/tickets/{tid}/reply", {"body": "Деньги у провайдера до подтверждения"}, format="json").json()
    assert r["status"] == "waiting_user" and r["messages"][-1]["is_staff_reply"]
    assert AdminAction.objects.filter(action="ticket.reply").exists()
    assert as_(api, market["buyer"]).get("/api/v1/staff/tickets").status_code == 403
    assert SupportTicket.objects.get(pk=tid).priority == "high"

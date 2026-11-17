import pytest

from accounts.models import User
from audit.services import record
from chats.models import ChatMessage
from orders.models import Order
from tests.test_phase6_orders import as_, paid_single

PUBLIC = "/api/v1/support/tickets"
STAFF = "/api/v1/staff/tickets"


@pytest.mark.django_db
def test_ticket_claim_scope_and_short_number(api, market, user_factory):
    order_id, _ = paid_single(api, market)
    buyer = market["buyer"]
    other = user_factory()
    first = user_factory(roles=("support_agent",))
    second = user_factory(roles=("support_agent",))
    body = {"category": "payment", "order_number": "#" + order_id[:8], "body": "Помогите разобраться с заказом."}
    assert as_(api, other).post(PUBLIC, body, format="json").status_code == 404
    result = as_(api, buyer).post(PUBLIC, body, format="json")
    assert result.status_code == 201, result.data
    ticket = result.data["id"]
    later = api.post(PUBLIC, {"category": "account", "body": "Нужна помощь со входом."}, format="json").data["id"]
    assert [row["id"] for row in api.get(PUBLIC).data["results"]] == [later, ticket]
    assert as_(api, other).get(f"{PUBLIC}/{ticket}").status_code == 404
    assert as_(api, other).get(STAFF).status_code == 403
    assert as_(api, first).get(STAFF, {"category": "payment"}).data["count"] == 1
    assert api.post(f"{STAFF}/{ticket}/reply", {"body": "Ответ"}, format="json").status_code == 403
    assert api.get("/api/v1/staff/orders", {"q": order_id[:8]}).data["results"][0]["id"] == order_id
    assert api.post(f"{STAFF}/{ticket}/assign").status_code == 200
    assert api.get(STAFF, {"category": "payment"}).data["count"] == 0
    assert api.get(STAFF, {"scope": "mine"}).data["results"][0]["id"] == ticket
    assert as_(api, second).get(STAFF, {"scope": "mine"}).data["count"] == 0
    assert api.get(f"{STAFF}/{ticket}").status_code == 404
    assert api.post(f"{STAFF}/{ticket}/assign").status_code == 409
    assert as_(api, first).post(f"{STAFF}/{ticket}/reply", {"body": "Посмотрели заказ."}, format="json").status_code == 200
    assert as_(api, buyer).get(f"{PUBLIC}/{ticket}").data["messages"][-1]["body"] == "Посмотрели заказ."
    assert api.post(f"{PUBLIC}/{ticket}", {"body": "Спасибо!"}, format="json").data["status"] == "in_progress"
    assert as_(api, first).post(f"{STAFF}/{ticket}/close").data["status"] == "closed"
    assert as_(api, buyer).post(f"{PUBLIC}/{ticket}", {"body": "Новый вопрос"}, format="json").status_code == 409


@pytest.mark.django_db
def test_staff_can_page_through_order_chat(api, market, user_factory):
    order_id, _ = paid_single(api, market)
    order = Order.objects.get(pk=order_id)
    ChatMessage.objects.bulk_create([ChatMessage(chat=order.chat, author=market["buyer"], body=f"Message {i}") for i in range(110)])
    as_(api, user_factory(roles=("support_agent",)))
    path = f"/api/v1/orders/{order_id}/chat"
    latest = api.get(path).data
    assert len(latest["results"]) == 100 and latest["next"]
    previous = api.get(path, {"before": latest["next"]}).data
    assert any(message["body"] == "Message 0" for message in previous["results"])
    assert not {m["id"] for m in latest["results"]}.intersection(m["id"] for m in previous["results"])


@pytest.mark.django_db
def test_owner_grant_requires_email_proof_and_role_changes_by_email(api, user_factory, settings):
    settings.SUPPORT_OWNER_EMAIL = "owner@example.com"
    owner = user_factory(email=settings.SUPPORT_OWNER_EMAIL)
    employee = user_factory()
    admin = user_factory(roles=("admin",))
    roles_url = "/api/v1/staff/support/roles"
    login_url = "/api/v1/auth/login"
    grant = {"email": employee.email.upper(), "role": "support_agent"}
    credentials = {"email": owner.email, "password": "Str0ng-pass-123", "staff_support": True}
    assert api.post(login_url, credentials, format="json").status_code == 403
    record(action="user.email_verified", subject_type="user", subject_id=owner.pk, actor=owner)
    session = api.post(login_url, credentials, format="json")
    assert session.status_code == 200, session.data
    assert "super_admin" in session.data["roles"]
    assert api.get("/api/v1/staff/arbitration").status_code == 200
    assert api.put(roles_url, grant, format="json").status_code == 200
    employee = User.objects.get(pk=employee.pk)
    assert employee.role_codes == {"buyer", "support_agent"}
    assert as_(api, admin).put(roles_url, grant, format="json").status_code == 403
    assert as_(api, owner).put(roles_url, {**grant, "enabled": False}, format="json").status_code == 200
    assert as_(api, User.objects.get(pk=employee.pk)).get(STAFF).status_code == 403


@pytest.mark.django_db
def test_order_complaints_and_tickets_share_staff_queue(api, market, user_factory):
    order_id, _ = paid_single(api, market)
    buyer, seller = market["buyer"], market["seller"]
    number = "#" + order_id[:8]
    options_url = "/api/v1/support/order-options"
    assert as_(api, user_factory()).get(options_url, {"number": number}).status_code == 404
    buyer_options = as_(api, buyer).get(options_url, {"number": number}).data
    seller_options = as_(api, seller).get(options_url, {"number": number}).data
    assert "seller_not_responding" in {row["code"] for row in buyer_options["reasons"]}
    assert "buyer_not_confirming" in {row["code"] for row in seller_options["reasons"]}
    assert "seller_not_responding" not in {row["code"] for row in seller_options["reasons"]}

    regular = as_(api, buyer).post(PUBLIC, {"category": "account", "body": "Нужна помощь со входом."}, format="json")
    assert regular.status_code == 201
    complaint = api.post(PUBLIC, {"category": "order", "order_number": number, "reason": "seller_not_responding",
                                  "body": "Продавец не отвечает после оплаты заказа."}, format="json")
    assert complaint.status_code == 201, complaint.data
    dispute_id = complaint.data["id"]
    assert complaint.data["kind"] == "dispute"
    assert as_(api, buyer).get(PUBLIC).data["results"][0]["id"] == dispute_id
    assert as_(api, seller).get(PUBLIC).data["results"][0]["id"] == dispute_id

    staff = user_factory(roles=("support_agent",))
    first_page = as_(api, staff).get(STAFF, {"page_size": 1}).data
    assert first_page["count"] == 2 and first_page["next"]
    assert first_page["results"][0]["reason"] == "Продавец не отвечает"
    next_page = api.get(STAFF, {"page_size": 1, "page": 2}).data
    assert next_page["results"][0]["id"] == regular.data["id"]
    assert api.get(STAFF, {"category": "account"}).data["results"][0]["kind"] == "ticket"
    assert api.get(STAFF, {"category": "order"}).data["results"][0]["id"] == dispute_id
    path = f"{STAFF}/{dispute_id}"
    assert api.get(path).data["messages"][0]["body"] == "Продавец не отвечает после оплаты заказа."
    assert api.post(path + "/assign").status_code == 200
    assert api.get(STAFF, {"group": "complaint"}).data["count"] == 0
    assert api.get(STAFF, {"scope": "mine"}).data["results"][0]["id"] == dispute_id
    assert as_(api, user_factory(roles=("support_agent",))).post(path + "/assign").status_code == 409


@pytest.mark.django_db
def test_arbitration_referral_claim_and_refund(api, market, user_factory, mock_provider):
    order_id, item_id = paid_single(api, market)
    support = user_factory(roles=("support_agent",))
    arbiter = user_factory(roles=("arbitrator",))
    second = user_factory(roles=("arbitrator",))
    buyer = market["buyer"]
    result = as_(api, buyer).post(PUBLIC, {
        "category": "refund", "order_number": order_id, "reason": "seller_not_responding",
        "body": "Прошу вернуть деньги, так как продавец не выходит на связь.",
    }, format="json")
    assert result.status_code == 201, result.data
    dispute_id = result.data["id"]
    arbitration = "/api/v1/staff/arbitration"
    detail = f"/api/v1/staff/disputes/{dispute_id}"
    ticket = f"{STAFF}/{dispute_id}"
    claim = f"{arbitration}/{dispute_id}/claim"
    assert as_(api, support).get(arbitration).status_code == 403
    assert api.get(STAFF, {"group": "refund"}).data["results"][0]["id"] == dispute_id
    assert api.post(ticket + "/assign").status_code == 200
    assert api.get(detail).status_code == 403
    assert api.post(ticket + "/refer", {"order": order_id}, format="json").status_code == 200
    assert api.get(ticket).status_code == 404
    assert api.get(STAFF, {"scope": "mine"}).data["count"] == 0
    assert api.post(claim).status_code == 403
    from accounts.roles import assign_role

    assign_role(buyer, "arbitrator")
    denied = as_(api, buyer).post(claim)
    assert denied.status_code == 403 and denied.data["error"]["code"] == "conflict_of_interest"
    assert as_(api, arbiter).get(arbitration).data["results"][0]["id"] == dispute_id
    assert api.get(detail).status_code == 403
    assert api.post(claim).status_code == 200
    assert api.get(arbitration).data["count"] == 0
    assert api.get(arbitration, {"scope": "mine"}).data["results"][0]["id"] == dispute_id
    assert as_(api, second).post(claim).status_code == 409
    assert api.get(detail).status_code == 403
    action = {"item": item_id, "decision": "full_refund", "comment": "Неисполненный заказ, одобрен полный возврат."}
    assert as_(api, support).post(detail + "/decide", action, format="json").status_code == 403
    mock_provider.fail_next = "refund"
    failed = as_(api, arbiter).post(detail + "/decide", action, format="json")
    assert failed.status_code == 200, failed.data
    assert failed.data["decisions"][-1]["actions"][0]["status"] == "failed"
    assert failed.data["items"][0]["active"] is True
    refund = api.post(detail + "/decide", action, format="json")
    assert refund.status_code == 200, refund.data
    assert refund.data["decisions"][-1]["actions"][0]["status"] == "done"


@pytest.mark.django_db
def test_support_can_close_order_complaint_without_refund(api, market, user_factory):
    from orders.models import OrderItem
    from payments.models import RefundRequest

    order_id, item_id = paid_single(api, market)
    buyer = market["buyer"]
    result = as_(api, buyer).post(PUBLIC, {
        "category": "order", "order_number": order_id, "reason": "seller_not_responding",
        "body": "Продавец не отвечал, хотелось бы уточнить сроки размещения.",
    }, format="json")
    assert result.status_code == 201, result.data
    ticket = f"{STAFF}/{result.data['id']}"
    support = user_factory(roles=("support_agent",))
    as_(api, support)
    assert api.post(ticket + "/assign").status_code == 200
    closed = api.post(ticket + "/close", {"order": order_id}, format="json")
    assert closed.status_code == 200, closed.data
    assert closed.data["status"] == "closed"
    assert OrderItem.objects.get(pk=item_id).status == "AWAITING_SELLER_ACCEPTANCE"
    assert not RefundRequest.objects.filter(order_item_id=item_id).exists()


@pytest.mark.django_db
def test_order_linked_ticket_can_be_referred(api, market, user_factory):
    order_id, _ = paid_single(api, market)
    buyer = market["buyer"]
    opened = as_(api, buyer).post(PUBLIC, {
        "category": "payment", "order_number": order_id, "body": "Оплата прошла, требуется проверка расчёта.",
    }, format="json")
    assert opened.status_code == 201, opened.data
    tid = opened.data["id"]
    support = user_factory(roles=("support_agent",))
    arbiter = user_factory(roles=("arbitrator",))
    ticket = f"{STAFF}/{tid}"
    assert as_(api, support).post(ticket + "/assign").status_code == 200
    assert api.post(ticket + "/refer", {"order": order_id}, format="json").status_code == 200
    assert api.get(ticket).status_code == 404
    disputes = as_(api, arbiter).get("/api/v1/staff/arbitration").data["results"]
    assert len(disputes) == 1
    detail = as_(api, buyer).get(f"{PUBLIC}/{tid}").data
    assert detail["arbitration_id"] == disputes[0]["id"]
    assert detail["status"] == "arbitration"
    assert api.get(PUBLIC).data["count"] == 1
    did = disputes[0]["id"]
    assert as_(api, arbiter).post(f"/api/v1/staff/arbitration/{did}/claim").status_code == 200
    closed = api.post(f"/api/v1/staff/disputes/{did}/close", {"comment": "Стороны договорились без возврата."}, format="json")
    assert closed.status_code == 200, closed.data
    assert as_(api, buyer).get(f"{PUBLIC}/{tid}").data["status"] == "closed"


@pytest.mark.django_db
def test_arbitration_waits_for_refund_confirmation(api, market, user_factory, mock_provider, django_capture_on_commit_callbacks):
    from payments.models import RefundRequest
    from payments.services import _finish_refund
    from support.models import Dispute, DisputeStatus

    order_id, item_id = paid_single(api, market)
    result = as_(api, market["buyer"]).post(PUBLIC, {
        "category": "refund", "order_number": order_id, "reason": "seller_not_responding",
        "body": "Прошу вернуть деньги за невыполненный заказ.",
    }, format="json")
    assert result.status_code == 201, result.data
    did = result.data["id"]
    support = user_factory(roles=("support_agent",))
    arbiter = user_factory(roles=("arbitrator",))
    assert as_(api, support).post(f"{STAFF}/{did}/assign").status_code == 200
    assert api.post(f"{STAFF}/{did}/refer").status_code == 200
    assert as_(api, arbiter).post(f"/api/v1/staff/arbitration/{did}/claim").status_code == 200
    case = f"/api/v1/staff/disputes/{did}"
    body = {"item": item_id, "decision": "full_refund", "comment": "Подтверждён невыполненный заказ."}
    mock_provider.fail_next = "timeout_refund"
    pending = api.post(case + "/decide", body, format="json")
    assert pending.status_code == 200, pending.data
    assert pending.data["decisions"][-1]["actions"][0]["status"] == "pending"
    assert pending.data["items"][0]["active"]
    assert api.post(case + "/decide", body, format="json").status_code == 409
    assert api.post(case + "/close", {"comment": "Закрытие без возврата."}, format="json").status_code == 409
    refund = RefundRequest.objects.get(order_item_id=item_id)
    with django_capture_on_commit_callbacks(execute=True):
        _finish_refund(refund.pk, "succeeded")
    assert Dispute.objects.get(pk=did).status == DisputeStatus.RESOLVED
    assert api.get(case).data["decisions"][-1]["actions"][0]["status"] == "done"

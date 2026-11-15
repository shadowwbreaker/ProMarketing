import pytest

from chats import conversations
from chats.services import system_message
from orders.models import Order

from .test_phase6_orders import TERMS, as_, create, item_url, paid_single, pay


@pytest.mark.django_db
def test_paid_order_inbox_and_received_orders(api, market, user_factory):
    buyer, seller = market["buyer"], market["seller"]
    brief = {**TERMS, "ad_text": "Текст рекламы", "links": ["https://example.com/brief"],
             "extra_requirements": "Добавить субтитры"}
    oid = create(api, buyer, offer=str(market["offers"][0].pk), terms=brief).json()["id"]
    status_url, inbox_url = "/api/v1/messages/status", "/api/v1/messages/orders"
    received_url, chat_url = "/api/v1/orders/received", f"/api/v1/orders/{oid}/chat"
    as_(api, seller)
    assert api.get(status_url).json() == {"unread": False, "has_received_orders": False,
                                        "signals": {"message": None, "order": None}}
    assert api.get(inbox_url).json()["results"] == []
    assert api.get(received_url).json()["count"] == 0

    payment = pay(api, buyer, oid)
    api.post(f"/api/v1/payments/mock/{payment}/complete", {"status": "succeeded"}, format="json")
    assert api.get(status_url).json()["has_received_orders"] is False

    as_(api, seller)
    unread = api.get(status_url).json()
    assert unread["unread"] and unread["has_received_orders"] and unread["signals"]["order"]
    thread, = api.get(inbox_url).json()["results"]
    assert (thread["order_id"], thread["role"], thread["unread"]) == (oid, "seller", 1)

    history = api.get(chat_url).json()["results"]
    received, = history
    assert received["author"]["id"] == str(buyer.pk)
    assert all(received["order_brief"][key] == value for key, value in brief.items())
    assert api.get(status_url).json()["unread"] is True
    assert api.get(chat_url + "?read=1").json()["marked_read"] == 1
    assert api.get(status_url).json() == {**unread, "unread": False}

    sales = api.get(received_url, {"number": oid[:8], "platform": market["accs"][0].platform}).json()
    assert sales["count"] == sales["summary"]["total"] == 1
    assert sales["summary"]["volume"] == sales["results"][0]["total_minor"]
    assert sales["results"][0]["id"] == oid
    assert oid.encode() in api.get(received_url, {"format_csv": "1"}).content

    as_(api, buyer)
    assert api.patch(f"{chat_url}/{received['id']}", {"body": "Замена"}, format="json").status_code == 403
    assert api.post(chat_url, {"body": "Уточнение к заказу"}, format="json").status_code == 201
    as_(api, seller)
    assert api.get(status_url).json()["unread"] is True
    assert api.get(chat_url + "?read=1").json()["results"][-1]["body"] == "Уточнение к заказу"

    as_(api, user_factory(roles=("buyer",)))
    assert api.get(inbox_url).json()["results"] == []
    assert api.get(received_url).json()["count"] == 0
    assert api.get(chat_url + "?read=1").status_code == 404


@pytest.mark.django_db
def test_conversation_merges_personal_history_and_two_paid_orders(api, market, user_factory, monkeypatch):
    buyer, seller = market["buyer"], market["seller"]
    other = user_factory(roles=("buyer",))
    body = "До покупки"
    assert as_(api, buyer).post(f"/api/v1/direct/{seller.pk}", {"body": body}, format="json").status_code == 201
    first, item = paid_single(api, market)
    second, _ = paid_single(api, market)
    legacy = Order.objects.get(pk=first)
    system_message(legacy, "Заказ создан. Условия зафиксированы.")
    system_message(legacy, "Канал: Оплата получена платёжным провайдером.")
    as_(api, seller)
    assert api.post(item_url(first, item, "accept")).status_code == 200
    concealed = "Чужая переписка"
    assert as_(api, other).post(f"/api/v1/direct/{seller.pk}", {"body": concealed}, format="json").status_code == 201

    as_(api, seller)
    inbox = "/api/v1/messages/conversations"
    rows = api.get(inbox).json()["results"]
    assert {row["user"]["id"] for row in rows} == {str(buyer.pk), str(other.pk)}
    assert len(rows) == 2 and all(row["unread"] for row in rows)
    url = f"{inbox}/{buyer.pk}"
    full = api.get(url, {"read": "1"}).json()
    assert [m["body"] for m in full["results"]] == [
        body, "Техническое задание к заказу", "Техническое задание к заказу", "Продавец принял заказ.",
    ]
    assert [o["id"] for o in full["orders"]] == [second, first]
    assert full["marked_read"] == 3
    assert api.get(url, {"read": "1", "version": full["version"]}).json() == {"unchanged": True}
    unread = {row["user"]["id"]: row["unread"] for row in api.get(inbox).json()["results"]}
    assert unread == {str(buyer.pk): False, str(other.pk): True}

    monkeypatch.setattr(conversations, "PAGE_SIZE", 2)
    latest = api.get(url).json()
    previous = api.get(url, {"before": latest["next"]}).json()
    assert len(latest["results"]) == len(previous["results"]) == 2
    assert [*previous["results"], *latest["results"]] == full["results"]

    as_(api, other)
    assert api.get(url).json()["results"] == []
    assert api.get(f"/api/v1/orders/{first}/chat").status_code == 404

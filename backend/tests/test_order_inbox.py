import pytest

from .test_phase6_orders import TERMS, as_, create, pay


@pytest.mark.django_db
def test_paid_order_inbox_and_received_orders(api, market, user_factory):
    buyer, seller = market["buyer"], market["seller"]
    brief = {**TERMS, "ad_text": "Текст рекламы", "links": ["https://example.com/brief"],
             "extra_requirements": "Добавить субтитры"}
    oid = create(api, buyer, offer=str(market["offers"][0].pk), terms=brief).json()["id"]
    status_url, inbox_url = "/api/v1/messages/status", "/api/v1/messages/orders"
    received_url, chat_url = "/api/v1/orders/received", f"/api/v1/orders/{oid}/chat"
    as_(api, seller)
    assert api.get(status_url).json() == {"unread": False, "has_received_orders": False}
    assert api.get(inbox_url).json()["results"] == []
    assert api.get(received_url).json()["count"] == 0

    payment = pay(api, buyer, oid)
    api.post(f"/api/v1/payments/mock/{payment}/complete", {"status": "succeeded"}, format="json")
    assert api.get(status_url).json()["has_received_orders"] is False

    as_(api, seller)
    assert api.get(status_url).json() == {"unread": True, "has_received_orders": True}
    thread, = api.get(inbox_url).json()["results"]
    assert (thread["order_id"], thread["role"], thread["unread"]) == (oid, "seller", 1)

    history = api.get(chat_url).json()["results"]
    paid, received = history[-2:]
    assert paid["kind"] == "system" and "Оплата получена" in paid["body"]
    assert received["author"]["id"] == str(buyer.pk)
    assert all(received["order_brief"][key] == value for key, value in brief.items())
    assert api.get(status_url).json()["unread"] is True
    assert api.get(chat_url + "?read=1").json()["marked_read"] == 1
    assert api.get(status_url).json() == {"unread": False, "has_received_orders": True}

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

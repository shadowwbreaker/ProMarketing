from datetime import timedelta

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from freezegun import freeze_time

from tests.test_phase6_orders import as_, item_url, paid_single

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                         "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


def chat(api, oid):
    return api.get(f"/api/v1/orders/{oid}/chat").json()


@pytest.mark.django_db
def test_chat_participants_only_with_system_messages(api, market, user_factory):
    oid, iid = paid_single(api, market)
    b = as_(api, market["buyer"])
    r = b.post(f"/api/v1/orders/{oid}/chat", {"body": "Здравствуйте! Когда сможете снять?"}, format="json")
    assert r.status_code == 201 and r.json()["warning"] == ""
    s = as_(api, market["seller"])
    s.post(f"/api/v1/orders/{oid}/chat", {"body": "Завтра"}, format="json")
    msgs = chat(s, oid)["results"]
    kinds = [(m["kind"], m["body"]) for m in msgs]
    assert ("system", "Заказ создан. Условия зафиксированы.") in kinds
    assert ("system", "Оплата получена платёжным провайдером.") in kinds
    assert [m["author"]["role"] for m in msgs if m["kind"] == "user"] == ["buyer", "seller"]
    assert "contact_signal" not in msgs[0]
    stranger = user_factory()
    assert as_(api, stranger).get(f"/api/v1/orders/{oid}/chat").status_code == 404
    assert api.post(f"/api/v1/orders/{oid}/chat", {"body": "hi"}, format="json").status_code == 404
    support = user_factory(roles=("support_agent",))
    staff_view = as_(api, support).get(f"/api/v1/orders/{oid}/chat").json()["results"]
    assert len(staff_view) == len(msgs) and "contact_signal" in staff_view[0]  # arbitration sees history
    assert api.post(f"/api/v1/orders/{oid}/chat", {"body": "x"}, format="json").json()["error"]["code"] == "staff_use_dispute"
    from notifications.models import Notification

    assert Notification.objects.filter(user=market["seller"], type="chat.message").exists()


@pytest.mark.django_db
def test_off_platform_contact_is_flagged(api, market):
    oid, _ = paid_single(api, market)
    b = as_(api, market["buyer"])
    for text in ["Напиши мне в телеграм", "+7 (999) 123-45-67", "мой email test@mail.ru", "переведи на карту 4276 1234 5678 9012"]:
        r = b.post(f"/api/v1/orders/{oid}/chat", {"body": text}, format="json").json()
        assert r["warning"], text
    from chats.models import ChatMessage

    assert ChatMessage.objects.filter(chat__order_id=oid, contact_signal=True).count() == 4


@pytest.mark.django_db
def test_edit_keeps_history_and_lock_after_dispute(api, market):
    from chats.models import ChatMessageRevision
    from chats.services import lock_chat
    from orders.models import Order

    oid, _ = paid_single(api, market)
    b = as_(api, market["buyer"])
    mid = b.post(f"/api/v1/orders/{oid}/chat", {"body": "Первая версия"}, format="json").json()["id"]
    r = b.patch(f"/api/v1/orders/{oid}/chat/{mid}", {"body": "Вторая версия"}, format="json").json()
    assert r["body"] == "Вторая версия" and r["edited"]
    assert ChatMessageRevision.objects.get(message_id=mid).body == "Первая версия"
    assert as_(api, market["seller"]).patch(f"/api/v1/orders/{oid}/chat/{mid}", {"body": "x"}, format="json").status_code == 403
    b = as_(api, market["buyer"])
    lock_chat(Order.objects.get(pk=oid))
    assert b.patch(f"/api/v1/orders/{oid}/chat/{mid}", {"body": "после спора"}, format="json").json()["error"]["code"] == "chat_locked"
    assert b.delete(f"/api/v1/orders/{oid}/chat/{mid}").json()["error"]["code"] == "chat_locked"
    assert chat(b, oid)["locked"] is True


@pytest.mark.django_db
def test_edit_window_and_soft_delete(api, market):
    from django.utils import timezone

    oid, _ = paid_single(api, market)
    b = as_(api, market["buyer"])
    m1 = b.post(f"/api/v1/orders/{oid}/chat", {"body": "Удалю"}, format="json").json()["id"]
    assert b.delete(f"/api/v1/orders/{oid}/chat/{m1}").status_code == 204
    shown = [m for m in chat(b, oid)["results"] if m["id"] == m1][0]
    assert shown["body"] == "" and shown["deleted_at"]
    m2 = b.post(f"/api/v1/orders/{oid}/chat", {"body": "Старое"}, format="json").json()["id"]
    with freeze_time(timezone.now() + timedelta(minutes=16)):
        assert b.patch(f"/api/v1/orders/{oid}/chat/{m2}", {"body": "x"}, format="json").json()["error"]["code"] == "edit_window_passed"


@pytest.mark.django_db
def test_attachments_type_check_and_access(api, market, user_factory):
    oid, _ = paid_single(api, market)
    b = as_(api, market["buyer"])
    bad = b.post("/api/v1/files", {"file": SimpleUploadedFile("evil.png", b"<?php echo 1; ?>", content_type="image/png")}, format="multipart")
    assert bad.json()["error"]["code"] == "file_type_not_allowed"  # real type sniffed, not trusted from name/header
    up = b.post("/api/v1/files", {"file": SimpleUploadedFile("shot.png", PNG, content_type="image/png")}, format="multipart").json()
    assert up["mime"] == "image/png" and len(up["sha256"]) == 64
    r = b.post(f"/api/v1/orders/{oid}/chat", {"body": "скрин", "attachments": [up["id"]]}, format="json").json()
    assert r["attachments"][0]["id"] == up["id"]
    seller = as_(api, market["seller"])
    resp = seller.get(f"/api/v1/files/{up['id']}")
    assert resp.status_code == 200 and b"".join(resp.streaming_content) == PNG
    assert resp["X-Content-Type-Options"] == "nosniff"
    assert as_(api, user_factory()).get(f"/api/v1/files/{up['id']}").status_code == 404
    other = user_factory()
    foreign = as_(api, other).post("/api/v1/files", {"file": SimpleUploadedFile("a.png", PNG)}, format="multipart").json()
    r = as_(api, market["buyer"]).post(f"/api/v1/orders/{oid}/chat", {"body": "x", "attachments": [foreign["id"]]}, format="json")
    assert r.json()["error"]["code"] == "bad_attachment"  # cannot attach someone else's file


@pytest.mark.django_db(transaction=True)
def test_notifications_and_email(api, market):
    from notifications.models import Notification
    from orders.services import notify_deadlines_soon

    oid, iid = paid_single(api, market)
    assert any("Новый оплаченный заказ" in m.subject for m in mail.outbox)
    as_(api, market["seller"]).post(item_url(oid, iid, "accept"))
    from django.utils import timezone

    from orders.models import OrderItem

    deadline = OrderItem.objects.get(pk=iid).publish_deadline
    assert notify_deadlines_soon(deadline - timedelta(hours=10)) == 1
    assert notify_deadlines_soon(deadline - timedelta(hours=9)) == 0  # only once
    assert notify_deadlines_soon(timezone.now()) == 0
    b = as_(api, market["buyer"])
    unread = b.get("/api/v1/me/notifications/unread-count").json()["unread"]
    assert unread >= 2
    assert b.post("/api/v1/me/notifications/read-all").json()["marked"] == unread
    assert b.get("/api/v1/me/notifications/unread-count").json()["unread"] == 0
    types = set(Notification.objects.values_list("type", flat=True))
    assert {"order.new", "order.paid", "order.accepted", "order.deadline_soon"} <= types

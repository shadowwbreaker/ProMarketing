from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier
from unittest.mock import MagicMock

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from rest_framework.test import APIClient

from accounts.models import EmailToken
from accounts.services import DUMMY_MAIL_BACKEND
from audit.services import record
from common.exceptions import DomainError
from files.models import Attachment
from files.scanner import scan
from orders.models import Order
from tests.test_phase2_auth import PWD, register
from tests.test_phase6_orders import TERMS, as_, paid_single
from tests.test_phase8_chat import PNG
from tests.test_phase15_2fa import code_for


@pytest.mark.django_db
def test_login_and_signup_reject_anonymous_csrf(user_factory):
    user = user_factory()
    client = APIClient(enforce_csrf_checks=True)
    credentials = {"email": user.email, "password": PWD}
    client.get("/api/v1/auth/csrf")
    token = client.cookies["csrftoken"].value
    assert client.post("/api/v1/auth/login", credentials, format="json").status_code == 403
    response = client.post("/api/v1/auth/login", credentials, HTTP_ORIGIN="https://different.example",
                           HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 403
    assert client.get("/api/v1/auth/session").json()["user"] is None
    assert client.post("/api/v1/auth/register", {}, format="json").status_code == 403
    response = client.post("/api/v1/auth/login", credentials, format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200


@pytest.mark.django_db
def test_legacy_staff_session_cannot_access_objects(api, market, user_factory, settings):
    settings.STAFF_2FA_REQUIRED = True
    order_id, _ = paid_single(api, market)
    upload = api.post("/api/v1/files", {"file": SimpleUploadedFile("image.png", PNG)}, format="multipart").json()
    public_paths = [f"/api/v1/orders/{order_id}", f"/api/v1/orders/{order_id}/chat", f"/api/v1/files/{upload['id']}"]
    admin = user_factory(roles=("admin",), is_staff=True, is_superuser=True)
    stale_session = as_(APIClient(), admin)
    client = as_(APIClient(), admin)
    assert client.get("/django-admin/login/").status_code == 404
    for url in public_paths:
        assert client.get(url).json()["error"]["code"] == "2fa_required"
    secret = client.post("/api/v1/me/2fa/setup").json()["secret"]
    assert client.post("/api/v1/me/2fa/confirm", {"code": code_for(secret)}, format="json").status_code == 200
    for url in public_paths:
        assert stale_session.get(url).json()["error"]["code"] == "2fa_required"
        assert client.get(url).status_code == 200
    client.logout()
    login = client.post("/api/v1/auth/login", {"email": admin.email, "password": PWD, "otp": code_for(secret, 30)},
                        format="json")
    assert login.status_code == 200
    assert client.get(public_paths[0]).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_parallel_order_retries_return_same_order(market, user_factory):
    buyer = market["buyer"]
    offer = market["offers"][0]
    payload = {"terms": TERMS, "offer": str(offer.pk)}
    barrier = Barrier(2)
    key = "original-order-retry-01"

    def post():
        close_old_connections()
        try:
            client = as_(APIClient(), buyer)
            barrier.wait(timeout=10)
            response = client.post("/api/v1/orders", payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
            return response.status_code, response.json()["id"]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(post), pool.submit(post)
        assert first.result(timeout=15) == second.result(timeout=15)
    assert Order.objects.filter(buyer=buyer).count() == 1
    client = as_(APIClient(), buyer)
    edited = {**payload, "terms": {**TERMS, "brand": "Changed brand"}}
    response = client.post("/api/v1/orders", edited, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert response.status_code == 409 and response.json()["error"]["code"] == "idempotency_conflict"
    assert client.post("/api/v1/orders", payload, format="json", HTTP_IDEMPOTENCY_KEY="x" * 129).status_code == 400
    assert client.post("/api/v1/orders", payload, format="json", HTTP_IDEMPOTENCY_KEY="new-key").status_code == 201
    other = as_(APIClient(), user_factory())
    assert other.post("/api/v1/orders", payload, format="json", HTTP_IDEMPOTENCY_KEY=key).status_code == 201


@pytest.mark.django_db
def test_attachment_validation_and_quarantine(api, user_factory, settings):
    settings.ATTACHMENT_CLAMAV_HOST = ""
    user = user_factory()
    client = as_(api, user)

    def upload(name, data):
        return client.post("/api/v1/files", {"file": SimpleUploadedFile(name, data)}, format="multipart")

    assert upload("broken.png", b"\x89PNG\r\n\x1a\n" + b"invalid").json()["error"]["code"] == "invalid_image"
    assert upload("file.pdf", b"%PDF-1.4").json()["error"]["code"] == "file_scan_required"
    marker = b"executable-looking data hiding after IEND"
    response = upload("image.png", PNG + marker)
    assert response.status_code == 201
    url = "/api/v1/files/" + response.json()["id"]
    assert marker not in b"".join(client.get(url).streaming_content)
    migration = import_module("files.migrations.0003_quarantine_unscanned_attachments")
    from django.apps import apps

    migration.quarantine_unscanned_attachments(apps, connection.schema_editor())
    assert Attachment.objects.get().scan_status == Attachment.ScanStatus.PENDING
    assert client.get(url).status_code == 404


@pytest.mark.parametrize(("reply", "expected"), [
    (b"stream: OK\0", None),
    (b"stream: Eicar-Signature FOUND\0", "unsafe_file"),
    (b"INSTREAM size limit exceeded. ERROR\0", "file_scan_unavailable"),
    (b"stream: OK", "file_scan_unavailable"),
])
def test_clamav_verdict_is_fail_closed(monkeypatch, settings, reply, expected):
    settings.ATTACHMENT_CLAMAV_HOST = "scanner.internal"
    sock = MagicMock()
    sock.__enter__.return_value = sock
    sock.recv.side_effect = [reply, b""]
    monkeypatch.setattr("files.scanner.socket.create_connection", lambda *a, **kw: sock)
    if expected:
        with pytest.raises(DomainError) as exc:
            scan(b"test")
        assert exc.value.code == expected
    else:
        scan(b"test")
    assert [call.args[0] for call in sock.sendall.call_args_list] == [
        b"zINSTREAM\0", b"\0\0\0\x04test", b"\0\0\0\0",
    ]


@pytest.mark.django_db(transaction=True)
def test_beta_never_autoverifies_and_can_resend_after_smtp_outage(api, settings):
    settings.BETA_MODE = True
    settings.DEV_AUTO_VERIFY_EMAIL = True
    settings.EMAIL_BACKEND = DUMMY_MAIL_BACKEND
    response = register(api)
    assert response.status_code == 201 and not response.json()["is_email_verified"]
    assert api.post("/api/v1/auth/resend-verification").status_code == 503
    assert not EmailToken.objects.exists()
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    assert api.post("/api/v1/auth/resend-verification").status_code == 200
    token = mail.outbox[-1].body.split("token=")[1]
    assert api.post("/api/v1/auth/verify-email", {"token": token}, format="json").status_code == 200
    assert api.get("/api/v1/me").json()["is_email_verified"]


@pytest.mark.django_db
def test_legacy_email_migration_preserves_real_verification(user_factory):
    from django.apps import apps

    automatic, proven, seeded = user_factory(), user_factory(), user_factory()
    for user in (automatic, proven):
        record(action="user.registered", subject_type="user", subject_id=user.pk, actor=user)
    record(action="user.email_verified", subject_type="user", subject_id=proven.pk, actor=proven)
    migration = import_module("accounts.migrations.0006_reverify_legacy_signup_emails")
    migration.reverify_legacy_signup_emails(apps, connection.schema_editor())
    for user in (automatic, proven, seeded):
        user.refresh_from_db()
    assert not automatic.is_email_verified
    assert proven.is_email_verified and seeded.is_email_verified

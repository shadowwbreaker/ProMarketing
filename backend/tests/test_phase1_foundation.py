import importlib
import json

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, connection, transaction

from common.hashchain import compute_hash
from common.money import platform_fee, split_amount


# --- health / API format -----------------------------------------------------
@pytest.mark.django_db
def test_health_live_and_ready(api):
    r = api.get("/api/v1/health/live")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r.headers["X-Request-ID"]
    r = api.get("/api/v1/health/ready")
    assert r.status_code == 200
    assert r.json()["checks"] == {"database": "ok", "cache": "ok"}


@pytest.mark.django_db
def test_error_format_and_request_id(api):
    r = api.get("/api/v1/health/does-not-exist", HTTP_X_REQUEST_ID="abc123")
    assert r.status_code == 404
    assert r.headers["X-Request-ID"] == "abc123"


@pytest.mark.django_db
def test_schema_generates(api):
    r = api.get("/api/schema/")
    assert r.status_code == 200
    assert b"ProMarketing API" in r.content


# --- money (D-005, D-015) ----------------------------------------------------
def test_platform_fee_five_percent_rounded_down():
    assert platform_fee(100_000) == 5_000
    assert platform_fee(1_999) == 99  # 99.95 -> 99, in favour of seller
    assert split_amount(150_000) == (7_500, 142_500)
    with pytest.raises(ValueError):
        platform_fee(-1)
    with pytest.raises(ValueError):
        platform_fee(100, fee_bps=10_001)


# --- audit log: append-only + hash chain (D-011) ------------------------------
@pytest.mark.django_db(transaction=True)
def test_audit_chain_and_append_only():
    from audit.models import AuditLog
    from audit.services import record, verify_chain

    a = record(action="test.one", subject_type="x", subject_id="1")
    b = record(action="test.two", subject_type="x", subject_id="2", comment="c")
    assert b.prev_hash == a.hash and b.seq == a.seq + 1
    assert verify_chain() == (True, None)

    with pytest.raises(PermissionError):
        a.comment = "tampered"
        a.save()
    with pytest.raises(PermissionError):
        AuditLog.objects.filter(pk=a.pk).update(comment="x")
    with pytest.raises(PermissionError):
        a.delete()
    # DB-level trigger blocks raw SQL tampering too
    with pytest.raises(Exception, match="append-only"):
        with transaction.atomic(), connection.cursor() as cur:
            cur.execute("UPDATE audit_auditlog SET comment='hack' WHERE id=%s", [a.pk])


def test_hashchain_deterministic():
    assert compute_hash("0", {"a": 1, "b": 2}) == compute_hash("0", {"b": 2, "a": 1})
    assert compute_hash("0", {"a": 1}) != compute_hash("1", {"a": 1})


# --- DB constraints -----------------------------------------------------------
@pytest.mark.django_db
def test_social_account_unique_and_single_active_job(user_factory):
    from social_data.models import SocialAccount, StatsRefreshJob

    u1, u2 = user_factory(roles=("seller",)), user_factory(roles=("seller",))
    acc = SocialAccount.objects.create(owner=u1, platform="tiktok", external_id="E1", handle="h",
                                       profile_url="https://www.tiktok.com/@h", title="h")
    with pytest.raises(IntegrityError), transaction.atomic():
        SocialAccount.objects.create(owner=u2, platform="tiktok", external_id="E1", handle="h",
                                     profile_url="https://www.tiktok.com/@h", title="h")
    StatsRefreshJob.objects.create(social_account=acc, requested_by=u1, trigger="user_refresh")
    with pytest.raises(IntegrityError), transaction.atomic():
        StatsRefreshJob.objects.create(social_account=acc, requested_by=u1, trigger="user_refresh")
    StatsRefreshJob.objects.filter(social_account=acc).update(status="succeeded")
    StatsRefreshJob.objects.create(social_account=acc, requested_by=u1, trigger="user_refresh")  # allowed now


@pytest.mark.django_db
def test_order_constraints(user_factory):
    from orders.models import Order

    u = user_factory()
    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.create(buyer=u, seller=u, fee_bps=500)


@pytest.mark.django_db
def test_seed_data_present():
    from accounts.models import Role
    from support.models import DisputeReason

    assert set(Role.objects.values_list("code", flat=True)) == {"buyer", "seller", "support_agent", "moderator", "admin", "super_admin"}
    assert DisputeReason.objects.filter(allowed_for__in=["buyer", "both"]).count() == 13  # roadmap 9.2


# --- RBAC matrix (D-012) -----------------------------------------------------
def test_rbac_matrix():
    from accounts.roles import permissions_for_roles

    assert "finance.refund" not in permissions_for_roles({"support_agent", "moderator"})
    assert "finance.refund" in permissions_for_roles({"admin"})
    assert "settings.security" in permissions_for_roles({"super_admin"})
    assert "settings.security" not in permissions_for_roles({"admin"})
    assert "staff.access" not in permissions_for_roles({"buyer", "seller"})


# --- adapters ---------------------------------------------------------------
def test_url_parser():
    from social_data.core.errors import InvalidProfileUrl
    from social_data.core.url_parser import detect_platform

    assert detect_platform("https://www.tiktok.com/@some.user") == ("tiktok", "some.user")
    assert detect_platform("https://instagram.com/brand_x/") == ("instagram", "brand_x")
    assert detect_platform("https://www.youtube.com/@channel-1") == ("youtube", "channel-1")
    assert detect_platform("https://youtube.com/channel/UC" + "a" * 22) == ("youtube", "UC" + "a" * 22)
    for bad in ["ftp://tiktok.com/@x", "https://evil.com/@x", "https://www.instagram.com/p/", "https://www.tiktok.com/x", "javascript:alert(1)"]:
        with pytest.raises(InvalidProfileUrl):
            detect_platform(bad)


def test_mock_payment_webhook_signature_and_idempotency():
    from payments.providers.base import WebhookSignatureError
    from payments.providers.mock import MockPaymentProvider

    p = MockPaymentProvider(secret="s")
    s1 = p.create_payment(order_id="o", amount_minor=1000, currency="RUB", idempotency_key="k1", return_url="http://x")
    s2 = p.create_payment(order_id="o", amount_minor=1000, currency="RUB", idempotency_key="k1", return_url="http://x")
    assert s1 == s2
    headers, body = p.simulate_payment(s1.provider_payment_id)
    ev = p.verify_webhook(headers, body)
    assert ev.type == "payment.succeeded"
    with pytest.raises(WebhookSignatureError):
        p.verify_webhook({"X-Mock-Signature": "bad"}, body)
    with pytest.raises(WebhookSignatureError):
        p.verify_webhook(headers, body.replace(b"succeeded", b"cancelled"))
    r1 = p.request_refund(provider_payment_id=s1.provider_payment_id, amount_minor=300, idempotency_key="r1", reason="x")
    r1b = p.request_refund(provider_payment_id=s1.provider_payment_id, amount_minor=300, idempotency_key="r1", reason="x")
    assert r1 == r1b and p.payments[s1.provider_payment_id]["refunded"] == 300  # no double refund
    with pytest.raises(ValueError):
        p.request_refund(provider_payment_id=s1.provider_payment_id, amount_minor=800, idempotency_key="r2", reason="x")
    assert p.capabilities.supports_d014() == (True, [])


def test_mock_provider_forbidden_in_production(settings):
    from payments.providers.mock import MockPaymentProvider

    settings.ENV = "production"
    with pytest.raises(ImproperlyConfigured):
        MockPaymentProvider()


def _load_prod():
    import sys

    for mod in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(mod, None)
    importlib.import_module("config.settings.prod")


def test_prod_settings_refuse_mock_and_fake(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 50)
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "k")
    monkeypatch.setenv("PAYMENT_PROVIDER", "mock")
    monkeypatch.setenv("SOCIAL_PROVIDER_MODE", "official")
    with pytest.raises(ImproperlyConfigured, match="Mock payment"):
        _load_prod()
    monkeypatch.setenv("PAYMENT_PROVIDER", "yookassa")
    monkeypatch.setenv("SOCIAL_PROVIDER_MODE", "fake")
    with pytest.raises(ImproperlyConfigured, match="Fake social"):
        _load_prod()
    monkeypatch.setenv("SOCIAL_PROVIDER_MODE", "official")
    _load_prod()  # valid production config loads
    monkeypatch.setenv("DJANGO_SECRET_KEY", "dev-insecure")
    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_prod()


# --- background tasks policy (D-004) -----------------------------------------
FORBIDDEN_PERIODIC_MODULES = ("social_data",)


def test_no_periodic_tasks_touch_social_platforms():
    from config.celery import app

    schedule = app.conf.beat_schedule or {}
    for name, entry in schedule.items():
        task = entry["task"]
        assert not task.startswith(FORBIDDEN_PERIODIC_MODULES) or task in ALLOWED_SOCIAL_CLEANUP, (name, task)


ALLOWED_SOCIAL_CLEANUP = {"social_data.tasks.purge_expired_youtube_data"}  # deletion only, no fetching


def test_field_encryption_roundtrip():
    from common.crypto import decrypt, encrypt

    token = encrypt("secret-token")
    assert token != "secret-token" and decrypt(token) == "secret-token"
    assert json.dumps(encrypt(""))  # empty stays empty

import time

import pyotp
import pytest

from tests.test_phase6_orders import as_

PWD = "Str0ng-pass-123"


def code_for(secret, offset=0):
    return pyotp.TOTP(secret).at(int(time.time()) + offset)


@pytest.mark.django_db
def test_staff_requires_2fa_when_enabled(api, user_factory, settings):
    settings.STAFF_2FA_REQUIRED = True
    admin = user_factory(roles=("admin",))
    c = as_(api, admin)
    r = c.get("/api/v1/staff/dashboard")
    assert r.status_code == 403 and r.json()["error"]["code"] == "2fa_required"
    assert c.get("/api/v1/me/2fa").json() == {"enabled": False, "required": True}
    s = c.post("/api/v1/me/2fa/setup").json()
    assert s["otpauth_url"].startswith("otpauth://totp/ProMarketing")
    assert c.post("/api/v1/me/2fa/confirm", {"code": "000000"}, format="json").json()["error"]["code"] == "invalid_otp"
    assert c.post("/api/v1/me/2fa/confirm", {"code": code_for(s["secret"])}, format="json").json()["enabled"] is True
    assert c.get("/api/v1/staff/dashboard").status_code == 200
    buyer = user_factory()
    assert as_(api, buyer).get("/api/v1/me").status_code == 200  # regular users are not affected


@pytest.mark.django_db
def test_login_with_otp_and_replay_protection(api, user_factory):
    admin = user_factory(email="a2@example.com", roles=("admin",))
    c = as_(api, admin)
    s = c.post("/api/v1/me/2fa/setup").json()
    c.post("/api/v1/me/2fa/confirm", {"code": code_for(s["secret"])}, format="json")
    api.logout()
    r = api.post("/api/v1/auth/login", {"email": "a2@example.com", "password": PWD}, format="json")
    assert r.status_code == 401 and r.json()["error"]["code"] == "otp_required"
    assert api.post("/api/v1/auth/login", {"email": "a2@example.com", "password": PWD, "otp": "123456"},
                    format="json").json()["error"]["code"] == "invalid_otp"
    nxt = code_for(s["secret"], 30)  # next step (confirmation already consumed the current one)
    assert api.post("/api/v1/auth/login", {"email": "a2@example.com", "password": PWD, "otp": nxt}, format="json").status_code == 200
    api.logout()
    r = api.post("/api/v1/auth/login", {"email": "a2@example.com", "password": PWD, "otp": nxt}, format="json")
    assert r.json()["error"]["code"] == "invalid_otp"  # the same code cannot be reused


@pytest.mark.django_db
def test_disable_requires_password_and_code(api, user_factory):
    u = user_factory(roles=("support_agent",))
    c = as_(api, u)
    s = c.post("/api/v1/me/2fa/setup").json()
    c.post("/api/v1/me/2fa/confirm", {"code": code_for(s["secret"])}, format="json")
    assert c.post("/api/v1/me/2fa/disable", {"code": code_for(s["secret"], 30), "password": "wrong"}, format="json").status_code == 400
    assert c.post("/api/v1/me/2fa/disable", {"code": code_for(s["secret"], 30), "password": PWD}, format="json").json()["enabled"] is False
    from audit.models import AuditLog

    assert AuditLog.objects.filter(action__in=["user.2fa_enabled", "user.2fa_disabled"]).count() == 2


def test_beta_mode_allows_mock_payments_in_production_settings(monkeypatch):
    """D-025: BETA_MODE lets the production config run with simulated payments — and only with them."""
    import importlib
    import sys

    env = {"DJANGO_SECRET_KEY": "x" * 50, "FIELD_ENCRYPTION_KEY": "k", "S3_BUCKET": "b", "SOCIAL_PROVIDER_MODE": "official",
           "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend", "DJANGO_ALLOWED_HOSTS": "x.ru",
           "PAYMENT_PROVIDER": "mock", "BETA_MODE": "true"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    for m in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(m, None)
    importlib.import_module("config.settings.prod")  # does not raise
    monkeypatch.setenv("BETA_MODE", "false")
    for m in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(m, None)
    import pytest as _p

    with _p.raises(Exception, match="Mock payment"):
        importlib.import_module("config.settings.prod")
    for m in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(m, None)


def test_meta_endpoint(api):
    r = api.get("/api/v1/meta")
    assert r.status_code == 200 and r.json()["beta"] is False and "payment_provider" in r.json()


@pytest.mark.django_db
def test_beta_payment_survives_provider_restart(settings):
    from payments.providers.beta import BetaPaymentProvider

    settings.BETA_MODE = True
    payment = BetaPaymentProvider().create_payment(
        order_id="order", amount_minor=10000, currency="RUB", idempotency_key="pay-key",
        return_url="https://beta.example.com/orders/order",
    )
    fresh = BetaPaymentProvider()
    headers, payload = fresh.simulate_payment(payment.provider_payment_id)
    assert fresh.verify_webhook(headers, payload).type == "payment.succeeded"
    assert BetaPaymentProvider().get_payment_status(payment.provider_payment_id) == "succeeded"
    args = {"provider_payment_id": payment.provider_payment_id, "amount_minor": 3000,
            "idempotency_key": "refund-key", "reason": "test"}
    refund = BetaPaymentProvider().request_refund(**args)
    assert BetaPaymentProvider().request_refund(**args) == refund
    assert BetaPaymentProvider().get_refund_status(refund.provider_id) == "succeeded"
    payout = BetaPaymentProvider().request_payout(
        seller_ref="seller", amount_minor=7000, idempotency_key="payout-key",
    )
    assert BetaPaymentProvider().get_payout_status(payout.provider_id) == "succeeded"


@pytest.mark.django_db
def test_ops_tick_requires_cron_secret(api, monkeypatch):
    assert api.get("/api/v1/ops/tick").status_code == 403
    monkeypatch.setenv("CRON_SECRET", "s3cret-value")
    assert api.get("/api/v1/ops/tick", HTTP_AUTHORIZATION="Bearer wrong").status_code == 403
    r = api.get("/api/v1/ops/tick", HTTP_AUTHORIZATION="Bearer s3cret-value")
    assert r.status_code == 200 and all(v == "ok" for v in r.json()["ran"].values()), r.json()

import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

PWD = "Str0ng-pass-123"


def register(api, email="new@example.com", **extra):
    payload = {"email": email, "password": PWD, "display_name": "Новый", "accept_terms": True, **extra}
    return api.post("/api/v1/auth/register", payload, format="json")


def token_from_mail(idx=-1):
    return re.search(r"token=([\w\-]+)", mail.outbox[idx].body).group(1)


@pytest.mark.django_db(transaction=True)
def test_register_login_logout_flow(api):
    r = register(api, email="New@Example.com", as_seller=True)
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["email"] == "new@example.com"
    assert body["roles"] == ["buyer", "seller"]
    assert body["is_email_verified"] is False
    assert "account.manage_own" in body["permissions"]
    assert len(mail.outbox) == 1  # verification email sent after commit

    assert api.get("/api/v1/me").status_code == 200  # logged in after registration
    assert api.post("/api/v1/auth/logout").status_code == 204
    assert api.get("/api/v1/me").status_code == 403

    r = api.post("/api/v1/auth/login", {"email": "NEW@example.com", "password": PWD}, format="json")
    assert r.status_code == 200
    assert api.get("/api/v1/me").json()["email"] == "new@example.com"


@pytest.mark.django_db
def test_register_validation(api, user_factory):
    user_factory(email="taken@example.com")
    assert register(api, email="taken@example.com").json()["error"]["code"] == "email_taken"
    r = register(api, email="weak@example.com", password="1234567890")
    assert r.status_code == 400 and r.json()["error"]["code"] == "validation_error"
    r = register(api, email="x@example.com", accept_terms=False)
    assert r.status_code == 400


@pytest.mark.django_db
def test_login_wrong_password_and_blocked(api, user_factory):
    u = user_factory(email="b@example.com")
    r = api.post("/api/v1/auth/login", {"email": "b@example.com", "password": "wrong"}, format="json")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_credentials"
    u.status = "blocked"
    u.save()
    r = api.post("/api/v1/auth/login", {"email": "b@example.com", "password": PWD}, format="json")
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_blocked"


@pytest.mark.django_db
def test_blocked_user_existing_session_loses_access(api, user_factory):
    u = user_factory()
    api.force_login(u)
    assert api.get("/api/v1/me").status_code == 200
    u.status = "blocked"
    u.save()
    assert api.get("/api/v1/me").status_code == 403


@pytest.mark.django_db
def test_session_rotates_on_login(user_factory):
    user_factory(email="s@example.com")
    c = APIClient()
    c.get("/api/v1/auth/csrf")
    c.cookies["sessionid"] = "attacker-fixed-session"
    c.post("/api/v1/auth/login", {"email": "s@example.com", "password": PWD}, format="json")
    assert c.cookies["sessionid"].value != "attacker-fixed-session"


@pytest.mark.django_db
def test_csrf_enforced_for_session_requests(user_factory):
    u = user_factory()
    c = APIClient(enforce_csrf_checks=True)
    c.force_login(u)
    r = c.patch("/api/v1/me", {"profile": {"bio": "Hack"}}, format="json")
    assert r.status_code == 403
    c.get("/api/v1/auth/csrf")
    token = c.cookies["csrftoken"].value
    r = c.patch("/api/v1/me", {"profile": {"bio": "Ок"}}, format="json", HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 200 and r.json()["profile"]["bio"] == "Ок"


@pytest.mark.django_db(transaction=True)
def test_email_verification(api):
    register(api)
    token = token_from_mail()
    assert api.post("/api/v1/auth/verify-email", {"token": token}, format="json").status_code == 200
    assert api.get("/api/v1/me").json()["is_email_verified"] is True
    r = api.post("/api/v1/auth/verify-email", {"token": token}, format="json")  # one-time
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_token"


@pytest.mark.django_db
def test_password_reset_flow_invalidates_sessions(user_factory):
    user_factory(email="r@example.com")
    other_session = APIClient()
    other_session.post("/api/v1/auth/login", {"email": "r@example.com", "password": PWD}, format="json")
    assert other_session.get("/api/v1/me").status_code == 200

    c = APIClient()
    assert c.post("/api/v1/auth/password-reset", {"email": "r@example.com"}, format="json").status_code == 200
    assert c.post("/api/v1/auth/password-reset", {"email": "nobody@example.com"}, format="json").status_code == 200
    assert len(mail.outbox) == 1  # no enumeration: same response, mail only for real user
    token = token_from_mail()
    new = "An0ther-strong-pass"
    assert c.post("/api/v1/auth/password-reset/confirm", {"token": token, "new_password": new}, format="json").status_code == 200
    assert other_session.get("/api/v1/me").status_code == 403  # old sessions invalidated
    assert c.post("/api/v1/auth/login", {"email": "r@example.com", "password": new}, format="json").status_code == 200
    r = c.post("/api/v1/auth/password-reset/confirm", {"token": token, "new_password": "Yet-an0ther-pass"}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_password_reset_token_expires(user_factory):
    from freezegun import freeze_time

    user_factory(email="e@example.com")
    c = APIClient()
    with freeze_time("2026-11-07 10:00:00"):
        c.post("/api/v1/auth/password-reset", {"email": "e@example.com"}, format="json")
    token = token_from_mail()
    with freeze_time("2026-11-07 11:30:00"):
        r = c.post("/api/v1/auth/password-reset/confirm", {"token": token, "new_password": "An0ther-strong-pass"}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_password_change_keeps_current_session(api, user_factory):
    u = user_factory()
    api.force_login(u)
    r = api.post("/api/v1/auth/password-change", {"old_password": "bad", "new_password": "An0ther-strong-pass"}, format="json")
    assert r.status_code == 400
    r = api.post("/api/v1/auth/password-change", {"old_password": PWD, "new_password": "An0ther-strong-pass"}, format="json")
    assert r.status_code == 200
    assert api.get("/api/v1/me").status_code == 200


@pytest.mark.django_db
def test_cabinet_is_scoped_to_owner(api, user_factory):
    from notifications.models import Notification
    from orders.models import Order

    a, b = user_factory(), user_factory(roles=("buyer", "seller"))
    Order.objects.create(buyer=b, seller=a, fee_bps=500, status="PAID")
    n_b = Notification.objects.create(user=b, type="t", title="for b")
    api.force_login(a)
    assert api.get("/api/v1/me/purchases").json()["count"] == 0
    assert api.get("/api/v1/me/sales").json()["count"] == 1
    assert api.get("/api/v1/me/notifications").json()["count"] == 0
    assert api.post(f"/api/v1/me/notifications/{n_b.pk}/read").status_code == 404  # cannot touch others' data
    for path in ["accounts", "networks", "reviews", "tickets"]:
        assert api.get(f"/api/v1/me/{path}").status_code == 200


@pytest.mark.django_db
def test_unauthenticated_api_is_protected(api):
    for path in ["/api/v1/me", "/api/v1/me/purchases", "/api/v1/me/notifications"]:
        assert api.get(path).status_code == 403


@pytest.mark.django_db
def test_become_seller(api, user_factory):
    u = user_factory(roles=("buyer",))
    api.force_login(u)
    assert "seller" in api.post("/api/v1/me/become-seller").json()["roles"]


@pytest.mark.django_db
def test_role_management_requires_super_admin(api, user_factory):
    target = user_factory()
    for roles in [("buyer",), ("support_agent",), ("admin",)]:
        actor = user_factory(roles=roles)
        api.force_login(actor)
        r = api.put(f"/api/v1/staff/users/{target.pk}/roles", {"roles": ["support_agent"], "comment": "найм"}, format="json")
        assert r.status_code == 403, roles
    boss = user_factory(roles=("super_admin",))
    api.force_login(boss)
    r = api.put(f"/api/v1/staff/users/{target.pk}/roles", {"roles": ["buyer", "support_agent"], "comment": "найм"}, format="json")
    assert r.status_code == 200 and r.json()["roles"] == ["buyer", "support_agent"]
    from audit.models import AdminAction

    assert AdminAction.objects.filter(action="user.roles_changed", subject_id=str(target.pk)).exists()
    target.refresh_from_db()
    assert target.is_staff is True
    r = api.put(f"/api/v1/staff/users/{boss.pk}/roles", {"roles": ["admin"], "comment": "x" * 3}, format="json")
    assert r.json()["error"]["code"] == "self_demotion"


@pytest.mark.django_db
def test_auth_rate_limited(api, monkeypatch):
    from django.core.cache import cache
    from rest_framework.throttling import ScopedRateThrottle

    cache.clear()
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {**ScopedRateThrottle.THROTTLE_RATES, "auth": "3/min"})
    codes = [api.post("/api/v1/auth/login", {"email": "x@example.com", "password": "y"}, format="json").status_code for _ in range(5)]
    assert codes[-1] == 429

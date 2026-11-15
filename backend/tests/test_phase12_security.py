import uuid
from datetime import timedelta

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone

from tests.test_phase6_orders import as_, create, item_url, paid_single, to_confirmation

PUBLIC_PREFIXES = ("health/", "auth/", "catalog/", "sellers/", "ad-formats", "payments/webhooks/", "schema", "meta", "ops/")  # meta: public site flags (D-025)


def _walk(patterns, prefix=""):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern)


def _concrete(route: str) -> str:
    import re

    route = re.sub(r"<uuid:\w+>", str(uuid.uuid4()), route)
    route = re.sub(r"<str:\w+>", "decide", route)
    return "/" + route.replace("^", "").replace("$", "")


@pytest.mark.django_db
def test_anonymous_cannot_reach_private_endpoints(api):
    routes = [r for r in _walk(get_resolver().url_patterns) if r.startswith("api/")]
    assert len(routes) > 60
    for route in routes:
        rel = route[len("api/v1/"):] if route.startswith("api/v1/") else route[len("api/"):]
        url = _concrete(route)
        for method in ("get", "post"):
            r = getattr(api, method)(url, {}, format="json")
            assert r.status_code < 500, (url, method, r.status_code)
            if not rel.startswith(PUBLIC_PREFIXES):
                assert r.status_code in (401, 403, 404, 405), (url, method, r.status_code)


@pytest.mark.django_db
def test_security_headers(api):
    r = api.get("/api/v1/health/live")
    assert r["Content-Security-Policy"].startswith("default-src 'none'")
    assert r["X-Content-Type-Options"] == "nosniff" and r["Referrer-Policy"] and r["X-Frame-Options"] == "DENY"


@pytest.mark.django_db
def test_cross_user_access_is_denied(api, market, user_factory):
    oid, iid = paid_single(api, market)
    to_confirmation(api, market, oid, iid)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    from payments.models import Payout

    po = Payout.objects.get(order_item_id=iid)
    intruder = user_factory(roles=("buyer", "seller"))
    c = as_(api, intruder)
    for url in [f"/api/v1/orders/{oid}", f"/api/v1/orders/{oid}/chat", f"/api/v1/orders/{oid}/events", f"/api/v1/orders/{oid}/disputes",
                f"/api/v1/social-accounts/{market['accs'][0].pk}"]:
        assert c.get(url).status_code == 404, url
    assert c.post(f"/api/v1/me/payouts/{po.pk}/withdraw").status_code == 404
    assert c.post(f"/api/v1/orders/{oid}/pay").status_code in (404, 409)
    assert c.post(item_url(oid, iid, "review"), {"rating": 5}, format="json").status_code == 404


@pytest.mark.django_db
def test_xss_payload_stored_as_plain_text(api, market):
    oid, _ = paid_single(api, market)
    payload = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    as_(api, market["buyer"]).post(f"/api/v1/orders/{oid}/chat", {"body": payload}, format="json")
    r = as_(api, market["seller"]).get(f"/api/v1/orders/{oid}/chat")
    assert r["Content-Type"].startswith("application/json")
    assert any(m["body"] == payload for m in r.json()["results"])  # returned as data; React escapes on render


@pytest.mark.django_db
def test_limited_user_can_read_but_not_start_new_deals(api, market):
    from accounts.services import expire_sanctions

    seller = market["seller"]
    adm_user = market["buyer"].__class__.objects.create_user(email="adm@example.com", password="x" * 12)
    from accounts.roles import assign_role

    assign_role(adm_user, "admin")
    as_(api, adm_user).post(f"/api/v1/staff/users/{seller.pk}/limit", {"reason": "нарушение сроков", "days": 3}, format="json")
    seller.refresh_from_db()
    assert seller.status == "limited"
    s = as_(api, seller)
    assert s.get(f"/api/v1/social-accounts/{market['accs'][0].pk}").status_code == 200  # can read own data
    r = s.post(f"/api/v1/social-accounts/{market['accs'][0].pk}/offers", {"ad_format": "mention", "price_minor": 10_000}, format="json")
    assert r.status_code == 403
    assert create(api, seller, offer=str(market["offers"][0].pk)).status_code == 403
    assert expire_sanctions(timezone.now() + timedelta(days=4)) == 1
    seller.refresh_from_db()
    assert seller.status == "active"


@pytest.mark.django_db
def test_chat_rate_limit(api, market, monkeypatch):
    from django.core.cache import cache
    from rest_framework.throttling import ScopedRateThrottle

    cache.clear()
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {**ScopedRateThrottle.THROTTLE_RATES, "chat": "3/min"})
    oid, _ = paid_single(api, market)
    b = as_(api, market["buyer"])
    codes = [b.post(f"/api/v1/orders/{oid}/chat", {"body": f"msg {i}"}, format="json").status_code for i in range(5)]
    assert codes[:3] == [201, 201, 201] and codes[-1] == 429


@pytest.mark.django_db
def test_fraud_signals_are_signals_only(api, market, user_factory):
    oid, _ = paid_single(api, market)
    s = as_(api, market["seller"])
    for text in ["пиши в телеграм", "+7 999 111-22-33", "переведи на карту"]:
        s.post(f"/api/v1/orders/{oid}/chat", {"body": text}, format="json")
    acc = market["accs"][1]
    st = acc.current_statistics
    st.trust_status = "SUSPICIOUS"
    st.save()
    mod = as_(api, user_factory(roles=("moderator",)))
    r = mod.get("/api/v1/staff/fraud-signals").json()
    types = {x["type"] for x in r["results"]}
    assert {"off_platform_attempts", "suspicious_stats"} <= types
    market["seller"].refresh_from_db()
    assert market["seller"].status == "active"  # no automatic punishment
    assert as_(api, user_factory(roles=("support_agent",))).get("/api/v1/staff/fraud-signals").status_code == 403
    assert as_(api, market["buyer"]).get("/api/v1/staff/fraud-signals").status_code == 403

"""Security and performance hardening (2026-11-09): flood limits, proxy-aware client IP, constant query counts."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework.throttling import AnonRateThrottle

pytestmark = pytest.mark.django_db


@pytest.fixture
def tight_anon(monkeypatch):
    from django.core.cache import cache

    cache.clear()
    monkeypatch.setattr(AnonRateThrottle, "THROTTLE_RATES", {**AnonRateThrottle.THROTTLE_RATES, "anon": "5/min"})
    yield
    cache.clear()


def test_every_public_endpoint_is_flood_limited(tight_anon):
    c = APIClient()
    codes = [c.get("/api/v1/catalog/accounts").status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[-1] == 429


def test_spoofed_forwarded_for_does_not_bypass_limits(tight_anon):
    c = APIClient()
    codes = [c.get("/api/v1/catalog/accounts", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}").status_code for i in range(7)]
    assert codes[-1] == 429  # NUM_PROXIES=0 in dev/tests: X-Forwarded-For from the client is ignored


def test_security_headers_on_api(api):
    r = api.get("/api/v1/health/live")
    assert r["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in r["Content-Security-Policy"]
    assert r["X-Frame-Options"] == "DENY"


def test_catalog_query_count_does_not_grow_with_results(api, account_factory, offer_factory, user_factory):
    """Guards against N+1: 3 vs 15 listed channels from different sellers cost the same number of queries."""
    def make(n):
        for _ in range(n):
            owner = user_factory(roles=("buyer", "seller"))
            offer_factory(account_factory(owner, listed=True))

    make(3)
    with CaptureQueriesContext(connection) as small:
        assert api.get("/api/v1/catalog/accounts").status_code == 200
    make(12)
    with CaptureQueriesContext(connection) as big:
        r = api.get("/api/v1/catalog/accounts")
    assert r.status_code == 200 and r.json()["count"] >= 15
    assert len(big.captured_queries) <= len(small.captured_queries) + 2, (len(small), len(big))

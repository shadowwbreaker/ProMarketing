import pytest

from audit.models import AdminAction
from tests.test_phase6_orders import as_, item_url, paid_single, to_confirmation


@pytest.fixture
def team(user_factory):
    return {"support": user_factory(roles=("support_agent",)), "moderator": user_factory(roles=("moderator",)),
            "admin": user_factory(roles=("admin",)), "super": user_factory(roles=("super_admin",))}


@pytest.mark.django_db
def test_dashboard_counts_and_finance_visibility(api, market, team):
    oid, iid = paid_single(api, market)
    to_confirmation(api, market, oid, iid)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    d = as_(api, team["admin"]).get("/api/v1/staff/dashboard").json()
    assert d["completed_orders"] == 1 and d["sellers"] >= 1 and d["accounts"] == 3
    assert d["finance"]["payments_minor"] == 100_000 and d["finance"]["platform_fee_minor"] == 5_000
    s = as_(api, team["support"]).get("/api/v1/staff/dashboard").json()
    assert "finance" not in s  # financial data only with finance.view
    assert as_(api, market["buyer"]).get("/api/v1/staff/dashboard").status_code == 403


@pytest.mark.django_db
def test_endpoint_permission_matrix(api, market, team):
    acc = market["accs"][0]
    cases = [
        ("get", "/api/v1/staff/users", {"support", "admin", "super"}),
        ("get", "/api/v1/staff/accounts", {"moderator", "admin", "super"}),
        ("get", "/api/v1/staff/orders", {"support", "admin", "super"}),
        ("get", "/api/v1/staff/audit", {"admin", "super"}),
        ("get", f"/api/v1/staff/accounts/{acc.pk}", {"moderator", "admin", "super"}),
    ]
    for method, url, allowed in cases:
        for role, user in team.items():
            code = getattr(as_(api, user), method)(url).status_code
            assert (code == 200) == (role in allowed), (url, role, code)
    for user in (market["buyer"], market["seller"]):
        assert as_(api, user).get("/api/v1/staff/users").status_code == 403


@pytest.mark.django_db
def test_user_search_detail_block_unblock(api, market, team):
    a = as_(api, team["support"])
    r = a.get("/api/v1/staff/users", {"q": market["seller"].email}).json()
    assert r["count"] == 1
    a.get(f"/api/v1/staff/users/{market['seller'].pk}")
    assert AdminAction.objects.filter(action="staff.user_viewed").exists()  # access to personal data is logged
    assert a.post(f"/api/v1/staff/users/{market['buyer'].pk}/block", {"reason": "мошенничество"}, format="json").status_code == 403
    adm = as_(api, team["admin"])
    assert adm.post(f"/api/v1/staff/users/{market['buyer'].pk}/block", {"reason": "x"}, format="json").json()["error"]["code"] == "reason_required"
    r = adm.post(f"/api/v1/staff/users/{market['buyer'].pk}/block", {"reason": "Подтверждённое мошенничество"}, format="json").json()
    assert r["status"] == "blocked"
    login = api.post("/api/v1/auth/login", {"email": market["buyer"].email, "password": "Str0ng-pass-123"}, format="json")
    assert login.json()["error"]["code"] == "account_blocked"
    adm = as_(api, team["admin"])
    assert adm.post(f"/api/v1/staff/users/{market['buyer'].pk}/unblock", {"reason": "Ошибка модерации"}, format="json").json()["status"] == "active"
    detail = adm.get(f"/api/v1/staff/users/{market['buyer'].pk}").json()
    assert detail["sanctions"][0]["revoked_at"] is not None and "orders_as_buyer" in detail
    assert adm.post(f"/api/v1/staff/users/{team['support'].pk}/block", {"reason": "конфликт"}, format="json").status_code == 403
    assert AdminAction.objects.filter(action__in=["user.block", "user.unblock"]).count() == 2


@pytest.mark.django_db
def test_account_moderation(api, market, team):
    acc = market["accs"][0]
    st = acc.current_statistics
    st.trust_status = "SUSPICIOUS"
    st.save()
    m = as_(api, team["moderator"])
    r = m.post(f"/api/v1/staff/accounts/{acc.pk}/review", {"reason": "резкий рост"}, format="json").json()
    assert r["status"] == "under_review" and r["is_listed"] is False
    assert as_(api, market["buyer"]).get(f"/api/v1/catalog/accounts/{acc.pk}").status_code == 404
    m = as_(api, team["moderator"])
    r = m.post(f"/api/v1/staff/accounts/{acc.pk}/approve", {"reason": "владелец прислал аналитику"}, format="json").json()
    assert r["status"] == "active" and r["trust_status"] == "VERIFIED"
    r = m.post(f"/api/v1/staff/accounts/{acc.pk}/block", {"reason": "чужой аккаунт"}, format="json").json()
    assert r["status"] == "blocked"
    assert m.get("/api/v1/staff/accounts", {"status": "blocked"}).json()["count"] == 1
    assert len(m.get(f"/api/v1/staff/accounts/{acc.pk}").json()["history"]) == 1
    assert AdminAction.objects.filter(action__startswith="social_account.").count() == 3


@pytest.mark.django_db
def test_orders_list_and_filters(api, market, team):
    oid, _ = paid_single(api, market)
    s = as_(api, team["support"])
    assert s.get("/api/v1/staff/orders").json()["count"] == 1
    assert s.get("/api/v1/staff/orders", {"q": oid}).json()["count"] == 1
    assert s.get("/api/v1/staff/orders", {"q": market["buyer"].email}).json()["count"] == 1
    assert s.get("/api/v1/staff/orders", {"status": "COMPLETED"}).json()["count"] == 0
    assert s.get("/api/v1/staff/orders").json()["results"][0]["payment"] == "succeeded"


@pytest.mark.django_db(transaction=True)
def test_audit_log_view_and_integrity(api, market, team):
    as_(api, team["admin"]).post(f"/api/v1/staff/users/{market['buyer'].pk}/warning", {"reason": "предупреждение"}, format="json")
    r = as_(api, team["admin"]).get("/api/v1/staff/audit", {"staff": "1"}).json()
    e = [x for x in r["results"] if x["action"] == "user.warning"][0]
    assert e["actor"] == team["admin"].email and e["reason"] == "предупреждение"
    assert e["before"] == {"status": "active"} and e["after"] == {"status": "active"}
    assert as_(api, team["admin"]).get("/api/v1/staff/audit/verify").json()["ok"] is True

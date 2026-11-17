"""Security/business regressions from the November 17 audit and owner handover."""
import importlib
import re
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from rest_framework.test import APIRequestFactory

from accounts.models import User
from accounts.roles import P, assign_role
from common.throttles import AnonRateThrottle
from orders.models import Order, OrderItem
from payments.models import RefundRequest
from support.models import Dispute, DisputeItem
from tests.test_phase6_orders import as_, create, item_url, make_network, paid_single, pay


@pytest.mark.django_db
def test_counterclaim_keeps_every_network_item(api, market):
    net, _ = make_network(market)
    order = create(api, market["buyer"], network=str(net.pk)).data
    oid = order["id"]
    ids = [item["id"] for item in order["items"]]
    pay(api, market["buyer"], oid)
    for iid in ids:
        assert as_(api, market["seller"]).post(item_url(oid, iid, "accept")).status_code == 200
    body = {"category": "order", "order_number": oid, "reason": "not_published",
            "items": ids[:1], "body": "Видео по первой позиции не опубликовано."}
    first = as_(api, market["buyer"]).post("/api/v1/support/tickets", body, format="json")
    assert first.status_code == 201, first.data
    reply = as_(api, market["seller"]).post("/api/v1/support/tickets", {
        **body, "items": ids[:2], "reason": "beyond_brief",
        "body": "Встречная претензия по обеим позициям рекламной сетки.",
    }, format="json")
    assert reply.status_code == 201 and reply.data["id"] == first.data["id"]
    actual = DisputeItem.objects.filter(dispute_id=first.data["id"], is_active=True)
    assert set(map(str, actual.values_list("order_item_id", flat=True))) == set(ids[:2])
    assert OrderItem.objects.filter(pk__in=ids[:2], status="DISPUTED").count() == 2


@pytest.mark.django_db
def test_legacy_endpoint_cannot_skip_arbitration(api, market, user_factory):
    oid, iid = paid_single(api, market)
    case = as_(api, market["buyer"]).post(f"/api/v1/orders/{oid}/disputes/open", {
        "reason": "seller_not_responding", "description": "Оплата прошла, но продавец не отвечает.",
    }, format="json")
    assert case.status_code == 201
    did = case.data["id"]
    assert Dispute.objects.get(pk=did).intake_category == "order"
    # Old database rows with a blank category must be protected as well.
    Dispute.objects.filter(pk=did).update(intake_category="")
    path = f"/api/v1/staff/disputes/{did}"
    for roles in [("admin",), ("arbitrator",)]:
        user = user_factory(roles=roles)
        assert as_(api, user).get(path).status_code == 403
        assert api.post(path + "/decide", {"item": iid, "decision": "full_refund",
                                          "comment": "Попытка возврата без передачи дела."}, format="json").status_code == 403
    assert not RefundRequest.objects.exists()


@pytest.mark.django_db
def test_support_cannot_handle_own_order_or_own_ticket(api, market):
    oid, _ = paid_single(api, market)
    seller = market["seller"]
    assign_role(seller, "support_agent")
    case = as_(api, market["buyer"]).post("/api/v1/support/tickets", {
        "category": "order", "order_number": oid, "reason": "seller_not_responding",
        "body": "Жалоба на продавца, который также работает в поддержке.",
    }, format="json")
    did = case.data["id"]
    path = f"/api/v1/staff/tickets/{did}"
    assert as_(api, seller).post(path + "/assign").status_code == 403
    # Guard against a pre-existing assignment left by an older release.
    Dispute.objects.filter(pk=did).update(assignee=seller)
    assert api.post(path + "/close").status_code == 403
    assert api.post(path + "/refer").status_code == 403
    assert api.get("/api/v1/staff/tickets", {"scope": "mine"}).data["count"] == 0
    own = api.post("/api/v1/support/tickets", {"category": "general",
                                             "body": "Нужна помощь с моим собственным аккаунтом."}, format="json")
    assert api.post(f"/api/v1/staff/tickets/{own.data['id']}/assign").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("reason", [{"invalid": "type"}, ["invalid"], 42, None, ""])
def test_invalid_appeal_is_validation_error(api, market, reason):
    oid, _ = paid_single(api, market)
    case = as_(api, market["buyer"]).post("/api/v1/support/tickets", {
        "category": "order", "order_number": oid, "reason": "seller_not_responding",
        "body": "Продавец не отвечает после оплаты рекламного размещения.",
    }, format="json")
    result = api.post(f"/api/v1/disputes/{case.data['id']}/appeal", {"reason": reason}, format="json")
    assert result.status_code == 400, result.data


def test_parallel_limit_is_strict():
    class BurstLimit(AnonRateThrottle):
        rate = "25/min"

    def request(_):
        req = APIRequestFactory().get("/", REMOTE_ADDR="198.51.100.7")
        req.user = AnonymousUser()
        return BurstLimit().allow_request(req, None)

    with ThreadPoolExecutor(max_workers=16) as pool:
        answers = list(pool.map(request, range(120)))
    assert sum(answers) == 25


@pytest.mark.django_db
def test_owner_has_all_permissions_only_after_mail_proof(api, settings, django_capture_on_commit_callbacks):
    settings.SUPPORT_OWNER_EMAIL = "maxshishkin07@gmail.com"
    settings.DEV_AUTO_VERIFY_EMAIL = True
    assert not User.objects.filter(email=settings.SUPPORT_OWNER_EMAIL).exists()
    with django_capture_on_commit_callbacks(execute=True):
        result = api.post("/api/v1/auth/register", {
            "email": settings.SUPPORT_OWNER_EMAIL.upper(), "display_name": "Владелец",
            "password": "Owner-strong-password-2026", "accept_terms": True, "as_seller": False,
        }, format="json")
    assert result.status_code == 201, result.data
    owner = User.objects.get(email=settings.SUPPORT_OWNER_EMAIL)
    assert not owner.is_email_verified and "super_admin" not in owner.role_codes
    token = re.search(r"token=([A-Za-z0-9_-]+)", mail.outbox[-1].body).group(1)
    assert api.post("/api/v1/auth/verify-email", {"token": token}, format="json").status_code == 200
    owner = User.objects.get(pk=owner.pk)
    assert owner.is_email_verified and owner.is_staff and owner.has_role("super_admin")
    assert all(owner.has_perm_code(code) for code in P)
    assert api.get("/api/v1/staff/arbitration").status_code == 200


@pytest.mark.django_db
def test_sample_seed_requires_explicit_test_environment(settings):
    settings.ENABLE_TEST_FIXTURES = False
    with pytest.raises(CommandError):
        call_command("seed_demo")
    with pytest.raises(CommandError):
        call_command("seed_beta_catalog")
    assert not User.objects.exists()


@pytest.mark.django_db
def test_retire_seed_identities_preserves_real_user_and_order(api, user_factory, account_factory, offer_factory):
    demo = user_factory(email="demo-seller1@example.com", roles=("seller", "super_admin"))
    buyer = user_factory(email="real-buyer@example.org")
    owner = user_factory(email="maxshishkin07@gmail.com", is_email_verified=False)
    account = account_factory(demo, listed=True)
    offer = offer_factory(account)
    oid, _ = paid_single(api, {"buyer": buyer, "offers": [offer]})
    as_(api, demo)
    migration = importlib.import_module("accounts.migrations.0007_retire_seed_accounts")
    migration.retire_seed_accounts(apps, SimpleNamespace(connection=connection))
    assert not User.objects.filter(email="demo-seller1@example.com").exists()
    demo = User.objects.get(pk=demo.pk)
    assert not demo.is_active and not demo.is_staff and not demo.has_usable_password()
    assert not demo.user_roles.exists()
    assert api.get("/api/v1/me").status_code == 403
    assert Order.objects.filter(pk=oid, buyer=buyer, seller=demo).exists()
    account.refresh_from_db()
    offer.refresh_from_db()
    assert not account.is_listed and not offer.is_active
    owner.refresh_from_db()
    assert owner.is_active and not owner.is_email_verified
    assert User.objects.get(pk=buyer.pk).email == buyer.email
    migration.retire_seed_accounts(apps, SimpleNamespace(connection=connection))

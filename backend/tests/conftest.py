import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api():
    return APIClient(enforce_csrf_checks=False)


@pytest.fixture
def user_factory(db):
    from accounts.models import User, UserProfile
    from accounts.roles import assign_role

    counter = {"n": 0}

    def make(email=None, roles=("buyer",), password="Str0ng-pass-123", **extra):
        counter["n"] += 1
        email = email or f"user{counter['n']}@example.com"
        extra.setdefault("is_email_verified", True)
        user = User.objects.create_user(email=email, password=password, **extra)
        UserProfile.objects.create(user=user, display_name=email.split("@")[0])
        for r in roles:
            assign_role(user, r)
        return user

    return make


@pytest.fixture
def account_factory(db):
    from django.utils import timezone

    from social_data.models import SocialAccount, SocialAccountStatistics

    counter = {"n": 0}

    def make(owner, platform="tiktok", followers=50_000, avg_views=10_000, trust="VERIFIED", listed=False, **extra):
        counter["n"] += 1
        n = counter["n"]
        acc = SocialAccount.objects.create(owner=owner, platform=platform, external_id=f"ext-{n}", handle=f"acc{n}",
                                           profile_url=f"https://www.tiktok.com/@acc{n}", title=f"Аккаунт {n}", **extra)
        if followers is not None:
            st = SocialAccountStatistics.objects.create(
                social_account=acc, followers=followers, avg_views=avg_views, videos_in_sample=15 if avg_views else 0,
                source="official_api" if trust != "MANUAL" else "manual", trust_status=trust, fetched_at=timezone.now(),
                expires_at=timezone.now() + timezone.timedelta(days=30))
            acc.current_statistics = st
        acc.is_listed = listed
        acc.save()
        return acc

    return make


@pytest.fixture
def offer_factory(db):
    from catalog.models import AdvertisingOffer

    def make(account, price_minor=500_000, ad_format="integration", **extra):
        return AdvertisingOffer.objects.create(social_account=account, price_minor=price_minor, ad_format=ad_format, **extra)

    return make


@pytest.fixture(autouse=True)
def mock_provider():
    from payments.providers.mock import MockPaymentProvider
    from payments.providers.registry import set_payment_provider

    p = MockPaymentProvider()
    set_payment_provider(p)
    yield p
    set_payment_provider(None)


@pytest.fixture
def market(user_factory, account_factory, offer_factory):
    seller = user_factory(roles=("buyer", "seller"))
    buyer = user_factory(roles=("buyer",))
    accs = [account_factory(seller, listed=True) for _ in range(3)]
    offers = [offer_factory(a, price_minor=100_000 * (i + 1)) for i, a in enumerate(accs)]
    return {"seller": seller, "buyer": buyer, "accs": accs, "offers": offers}


@pytest.fixture(autouse=True)
def _reference_data(request):
    """Transactional tests TRUNCATE tables, wiping rows seeded by data migrations — restore them."""
    marker = request.node.get_closest_marker("django_db")
    if not marker:
        return
    if not marker.kwargs.get("transaction"):
        request.getfixturevalue("db")
    import importlib

    from django.apps import apps

    importlib.import_module("support.migrations.0002_seed_reasons").seed(apps, None)
    importlib.import_module("accounts.migrations.0003_seed_roles").seed(apps, None)

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
        user = User.objects.create_user(email=email, password=password, is_email_verified=True, **extra)
        UserProfile.objects.create(user=user, display_name=email.split("@")[0])
        for r in roles:
            assign_role(user, r)
        return user

    return make

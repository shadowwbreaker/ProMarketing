"""Public profile (FunPay-style), pre-order direct messages, dev email auto-verify, link parsing."""
import pytest
from django.test import override_settings

from accounts.models import User
from chats.models import DirectMessage, DirectThread
from social_data.core.url_parser import detect_platform

pytestmark = pytest.mark.django_db


def test_profile_has_rating_distribution_and_online(api, user_factory, account_factory, offer_factory):
    seller = user_factory(roles=("buyer", "seller"))
    acc = account_factory(seller, listed=True)
    offer_factory(acc)
    r = api.get(f"/api/v1/sellers/{seller.pk}")
    assert r.status_code == 200
    d = r.json()
    assert d["rating_distribution"] == {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    assert d["online"] is False and d["is_seller"] is True
    assert len(d["accounts"]) == 1


def test_direct_messages_between_two_users(api, user_factory):
    buyer, seller = user_factory(), user_factory(roles=("buyer", "seller"))
    api.force_authenticate(buyer)
    r = api.post(f"/api/v1/direct/{seller.pk}", {"body": "Здравствуйте, свободны на этой неделе?"}, format="json")
    assert r.status_code == 201 and r.json()["mine"] is True and r.json()["warning"] == ""
    api.post(f"/api/v1/direct/{seller.pk}", {"body": "пишите в телеграм"}, format="json")
    assert DirectThread.objects.count() == 1
    assert DirectMessage.objects.filter(contact_signal=True).count() == 1

    api.force_authenticate(seller)
    msgs = api.get(f"/api/v1/direct/{buyer.pk}").json()["results"]
    assert [m["mine"] for m in msgs] == [False, False]
    assert DirectMessage.objects.filter(read_at__isnull=True).count() == 0  # opened by recipient
    r = api.post(f"/api/v1/direct/{buyer.pk}", {"body": "Да"}, format="json")
    assert r.status_code == 201 and DirectThread.objects.count() == 1  # same thread from the other side
    threads = api.get("/api/v1/direct").json()["results"]
    assert len(threads) == 1 and threads[0]["user"]["id"] == str(buyer.pk)
    assert seller.notifications.filter(type="direct.message").count() == 2


def test_direct_rules(api, user_factory):
    u = user_factory()
    assert api.post(f"/api/v1/direct/{u.pk}", {"body": "x"}, format="json").status_code in (401, 403)
    api.force_authenticate(u)
    assert api.post(f"/api/v1/direct/{u.pk}", {"body": "x"}, format="json").status_code == 400  # not to self
    other = user_factory()
    assert api.post(f"/api/v1/direct/{other.pk}", {"body": "  "}, format="json").status_code == 400
    assert api.post(f"/api/v1/direct/{other.pk}", {"body": "x" * 2001}, format="json").status_code == 400


@override_settings(DEV_AUTO_VERIFY_EMAIL=True)
def test_dev_auto_verify_email(api):
    r = api.post("/api/v1/auth/register", {"email": "new@example.com", "password": "Str0ng-pass-123", "display_name": "Новый",
                                           "as_seller": False, "accept_terms": True}, format="json")
    assert r.status_code == 201
    assert User.objects.get(email="new@example.com").is_email_verified


def test_youtube_shorts_links_including_cyrillic_handles():
    assert detect_platform("https://www.youtube.com/@MrBeast/shorts") == ("youtube", "MrBeast")
    assert detect_platform("https://www.youtube.com/@%D0%BA%D0%B0%D0%BD%D0%B0%D0%BB/shorts") == ("youtube", "канал")
    assert detect_platform("https://www.youtube.com/@канал/shorts") == ("youtube", "канал")


def _yt_account(api, user, handle):
    api.force_authenticate(user)
    r = api.post("/api/v1/social-accounts", {"profile_url": f"https://www.youtube.com/@{handle}/shorts"}, format="json")
    assert r.status_code == 201, r.json()
    assert r.json()["ownership_verified"] is False and r.json()["ownership_check_supported"] is True
    return r.json()["id"]


def test_youtube_ownership_by_code_in_description(api, user_factory):
    seller = user_factory(roles=("buyer", "seller"))
    acc_id = _yt_account(api, seller, "mychannel")
    code = api.post(f"/api/v1/social-accounts/{acc_id}/ownership/start").json()["code"]
    assert code.startswith("PM-")
    assert api.post(f"/api/v1/social-accounts/{acc_id}/ownership/start").json()["code"] == code  # stable until verified
    r = api.post(f"/api/v1/social-accounts/{acc_id}/ownership/check")
    assert r.json()["verified"] is True and r.json()["account"]["ownership_verified"] is True
    assert r.json()["account"]["ownership_code"] == ""
    assert api.post(f"/api/v1/social-accounts/{acc_id}/ownership/start").status_code == 400  # already verified


def test_youtube_ownership_code_not_found(api, user_factory):
    seller = user_factory(roles=("buyer", "seller"))
    acc_id = _yt_account(api, seller, "someone_notmine")
    assert api.post(f"/api/v1/social-accounts/{acc_id}/ownership/check").status_code == 400  # no code yet
    api.post(f"/api/v1/social-accounts/{acc_id}/ownership/start")
    r = api.post(f"/api/v1/social-accounts/{acc_id}/ownership/check")
    assert r.status_code == 200 and r.json()["verified"] is False
    other = user_factory(roles=("buyer", "seller"))
    api.force_authenticate(other)
    assert api.post(f"/api/v1/social-accounts/{acc_id}/ownership/start").status_code == 404  # only the owner

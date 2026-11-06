import json
from datetime import timedelta

import httpx
import pytest
from django.utils import timezone
from freezegun import freeze_time

from social_data.core import errors
from social_data.core.registry import set_provider_override
from social_data.core.types import AccountStats
from social_data.models import SocialAccount, SocialAccountStatistics, StatsRefreshJob
from social_data.providers.fake.provider import FakeProvider
from social_data.services.refresh_service import average_views, display_status, run_job

TT = "https://www.tiktok.com/@creator_one"


@pytest.fixture
def seller(user_factory):
    return user_factory(roles=("buyer", "seller"))


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    for p in ("tiktok", "youtube", "instagram"):
        set_provider_override(p, None)


def add(api, url=TT, **extra):
    return api.post("/api/v1/social-accounts", {"profile_url": url, "category": "lifestyle", **extra}, format="json")


# --- formula -------------------------------------------------------------------
def test_average_formula_from_roadmap():
    assert average_views([10_000, 20_000, 30_000]) == 20_000
    assert average_views([5]) == 5
    assert average_views([]) is None
    assert average_views([1, 2]) == 1  # floor
    with pytest.raises(ValueError):
        average_views([-1])


# --- initial fetch -------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_add_account_fetches_once_and_saves_15_videos(api, seller):
    fake = FakeProvider("tiktok")
    set_provider_override("tiktok", fake)
    api.force_login(seller)
    r = add(api)
    assert r.status_code == 201, r.content
    acc = SocialAccount.objects.get(pk=r.json()["id"])
    stats = acc.current_statistics
    assert stats is not None and stats.videos_in_sample == 15
    views = list(stats.videos.values_list("views", flat=True))
    assert stats.avg_views == sum(views) // 15
    assert stats.trust_status == "VERIFIED"
    assert StatsRefreshJob.objects.filter(social_account=acc).count() == 1
    # exactly one cycle: resolve + stats + videos, nothing else afterwards
    assert [c.split(":")[0] for c in fake.calls] == ["resolve", "stats", "videos"]
    detail = api.get(f"/api/v1/social-accounts/{acc.pk}").json()
    assert detail["statistics"]["videos_in_sample"] == 15
    assert detail["refresh"]["last_job"]["status"] == "succeeded"


@pytest.mark.django_db(transaction=True)
def test_fewer_than_15_videos_average_over_actual(api, seller):
    set_provider_override("tiktok", FakeProvider("tiktok"))
    api.force_login(seller)
    r = add(api, url="https://www.tiktok.com/@small_fewvideos")
    s = SocialAccount.objects.get(pk=r.json()["id"]).current_statistics
    assert s.videos_in_sample == 3
    assert s.avg_views == sum(s.videos.values_list("views", flat=True)) // 3


@pytest.mark.django_db(transaction=True)
def test_no_videos_gives_null_average(api, seller):
    set_provider_override("tiktok", FakeProvider("tiktok"))
    api.force_login(seller)
    r = add(api, url="https://www.tiktok.com/@empty_novideos")
    s = SocialAccount.objects.get(pk=r.json()["id"]).current_statistics
    assert s.videos_in_sample == 0 and s.avg_views is None


# --- refresh limits --------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_refresh_interval_enforced_and_shown(api, seller):
    set_provider_override("tiktok", FakeProvider("tiktok"))
    api.force_login(seller)
    with freeze_time("2026-11-07 10:00:00"):
        acc_id = add(api).json()["id"]
        r = api.post(f"/api/v1/social-accounts/{acc_id}/refresh")
        assert r.status_code == 429
        assert r.json()["error"]["code"] == "rate_limited"
        assert r.json()["error"]["details"]["next_allowed_at"].startswith("2026-11-08T10:00")
    with freeze_time("2026-11-08 10:00:01"):
        r = api.post(f"/api/v1/social-accounts/{acc_id}/refresh")
        assert r.status_code == 202
    assert SocialAccountStatistics.objects.filter(social_account_id=acc_id).count() == 2  # history kept


@pytest.mark.django_db(transaction=True)
def test_concurrent_refresh_rejected(api, seller):
    set_provider_override("tiktok", FakeProvider("tiktok"))
    api.force_login(seller)
    acc_id = add(api).json()["id"]
    SocialAccount.objects.filter(pk=acc_id).update(last_refresh_requested_at=timezone.now() - timedelta(days=2))
    StatsRefreshJob.objects.create(social_account_id=acc_id, requested_by=seller, trigger="user_refresh")  # running elsewhere
    r = api.post(f"/api/v1/social-accounts/{acc_id}/refresh")
    assert r.status_code == 409 and r.json()["error"]["code"] == "refresh_in_progress"


@pytest.mark.django_db(transaction=True)
def test_duplicate_task_delivery_is_noop(api, seller):
    fake = FakeProvider("tiktok")
    set_provider_override("tiktok", fake)
    api.force_login(seller)
    acc_id = add(api).json()["id"]
    job = StatsRefreshJob.objects.get(social_account_id=acc_id)
    calls = len(fake.calls)
    run_job(job.pk)
    assert len(fake.calls) == calls
    assert SocialAccountStatistics.objects.filter(social_account_id=acc_id).count() == 1


# --- errors keep previous data ------------------------------------------------------
class FailingProvider(FakeProvider):
    def get_account_statistics(self, account, *, credentials=None):
        raise errors.ProviderUnavailable("down")


@pytest.mark.django_db(transaction=True)
def test_error_does_not_destroy_previous_statistics(api, seller):
    set_provider_override("tiktok", FakeProvider("tiktok"))
    api.force_login(seller)
    acc_id = add(api).json()["id"]
    before = SocialAccount.objects.get(pk=acc_id).current_statistics_id
    SocialAccount.objects.filter(pk=acc_id).update(last_refresh_requested_at=timezone.now() - timedelta(days=2))
    set_provider_override("tiktok", FailingProvider("tiktok"))
    assert api.post(f"/api/v1/social-accounts/{acc_id}/refresh").status_code == 202
    acc = SocialAccount.objects.get(pk=acc_id)
    assert acc.current_statistics_id == before
    detail = api.get(f"/api/v1/social-accounts/{acc_id}").json()
    assert detail["refresh"]["last_job"]["status"] == "failed"
    assert detail["refresh"]["last_job"]["error_code"] == "provider_unavailable"
    assert detail["statistics"]["trust_status"] == "VERIFIED"
    hist = api.get(f"/api/v1/social-accounts/{acc_id}/statistics").json()
    assert len(hist["results"]) == 1 and len(hist["failed_jobs"]) == 1


class GrowthProvider(FakeProvider):
    def get_account_statistics(self, account, *, credentials=None):
        return AccountStats(followers=50_000_000)


@pytest.mark.django_db(transaction=True)
def test_suspicious_growth_hides_account_for_review(api, seller):
    set_provider_override("tiktok", FakeProvider("tiktok"))
    api.force_login(seller)
    acc_id = add(api).json()["id"]
    SocialAccount.objects.filter(pk=acc_id).update(last_refresh_requested_at=timezone.now() - timedelta(days=2))
    set_provider_override("tiktok", GrowthProvider("tiktok"))
    api.post(f"/api/v1/social-accounts/{acc_id}/refresh")
    acc = SocialAccount.objects.get(pk=acc_id)
    assert acc.current_statistics.trust_status == "SUSPICIOUS"
    assert acc.status == "under_review"


# --- manual / stale / youtube display --------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_manual_account_is_marked_manual(api, seller):
    api.force_login(seller)
    r = add(api, url="https://www.youtube.com/@manualchannel", manual=True)
    assert r.status_code == 201
    acc_id = r.json()["id"]
    assert r.json()["statistics"]["trust_status"] == "UNAVAILABLE"
    r = api.post(f"/api/v1/social-accounts/{acc_id}/manual-statistics", {"followers": 1000, "video_views": [100, 200, 300]}, format="json")
    assert r.status_code == 201
    st = r.json()["statistics"]
    assert st["trust_status"] == "MANUAL" and st["avg_views"] == 200 and st["videos_in_sample"] == 3


@pytest.mark.django_db
def test_stale_and_youtube_derived_metric_rules(seller, settings):
    acc = SocialAccount.objects.create(owner=seller, platform="youtube", external_id="UCx", handle="c",
                                       profile_url="https://www.youtube.com/@c", title="c")
    now = timezone.now()
    s = SocialAccountStatistics.objects.create(social_account=acc, followers=10, avg_views=500, videos_in_sample=15,
                                               source="official_api", trust_status="VERIFIED", fetched_at=now,
                                               expires_at=now + timedelta(days=30))
    settings.YOUTUBE_DERIVED_METRICS_APPROVED = False
    assert display_status(s, "youtube", for_owner=True)["avg_views"] == 500
    public = display_status(s, "youtube", for_owner=False)
    assert public["avg_views"] is None and public["trust_status"] == "UNAVAILABLE"
    settings.YOUTUBE_DERIVED_METRICS_APPROVED = True
    assert display_status(s, "youtube", for_owner=False)["avg_views"] == 500
    with freeze_time(now + timedelta(days=31)):
        assert display_status(s, "tiktok", for_owner=False)["trust_status"] == "STALE"


@pytest.mark.django_db
def test_purge_expired_youtube_data(seller, settings):
    from social_data.tasks import purge_expired_youtube_data

    settings.YOUTUBE_DERIVED_METRICS_APPROVED = False
    acc = SocialAccount.objects.create(owner=seller, platform="youtube", external_id="UCy", handle="c",
                                       profile_url="https://www.youtube.com/@c", title="c")
    old = timezone.now() - timedelta(days=31)
    SocialAccountStatistics.objects.create(social_account=acc, followers=1, source="official_api", trust_status="VERIFIED", fetched_at=old)
    SocialAccountStatistics.objects.create(social_account=acc, followers=1, source="manual", trust_status="MANUAL", fetched_at=old)
    SocialAccountStatistics.objects.create(social_account=acc, followers=1, source="official_api", trust_status="VERIFIED", fetched_at=timezone.now())
    assert purge_expired_youtube_data() == 1
    assert SocialAccountStatistics.objects.filter(social_account=acc).count() == 2


# --- access control & platform rules --------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_access_rules(api, seller, user_factory):
    set_provider_override("tiktok", FakeProvider("tiktok"))
    buyer_only = user_factory(roles=("buyer",))
    api.force_login(buyer_only)
    assert add(api).status_code == 403  # needs seller permission
    api.force_login(seller)
    acc_id = add(api).json()["id"]
    assert add(api).json()["error"]["code"] == "account_exists"
    other = user_factory(roles=("seller",))
    api.force_login(other)
    for path in ["", "/statistics"]:
        assert api.get(f"/api/v1/social-accounts/{acc_id}{path}").status_code == 404
    assert api.post(f"/api/v1/social-accounts/{acc_id}/refresh").status_code == 404
    r = add(api, url="https://www.instagram.com/some_brand")
    assert r.status_code == 400 and r.json()["error"]["code"] == "platform_disabled"  # D-013
    assert add(api, url="https://evil.example.com/@x").json()["error"]["code"] == "invalid_profile_url"


# --- contract tests: TikTok Display API ------------------------------------------------
def tiktok_transport(state):
    def handler(request: httpx.Request):
        path = request.url.path
        state.append((request.method, path, request.url.params.get("fields")))
        if path == "/v2/oauth/token/":
            return httpx.Response(200, json={"access_token": "act.1", "refresh_token": "rft.1", "open_id": "OPEN1",
                                             "expires_in": 86400, "scope": "user.info.basic,user.info.stats,video.list"})
        if request.headers.get("Authorization") != "Bearer act.1":
            return httpx.Response(401, json={"error": {"code": "access_token_invalid"}})
        if path == "/v2/user/info/":
            return httpx.Response(200, json={"data": {"user": {"open_id": "OPEN1", "username": "creator_one",
                                                               "display_name": "Creator", "follower_count": 12345}},
                                             "error": {"code": "ok"}})
        if path == "/v2/video/list/":
            body = json.loads(request.content)
            cursor = body.get("cursor", 0)
            vids = [{"id": str(1000 + cursor + i), "view_count": (cursor + i + 1) * 100, "create_time": 1762000000 - i,
                     "share_url": f"https://www.tiktok.com/@creator_one/video/{1000 + cursor + i}", "duration": 20}
                    for i in range(body["max_count"])]
            return httpx.Response(200, json={"data": {"videos": vids, "cursor": cursor + len(vids), "has_more": True},
                                             "error": {"code": "ok"}})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def test_tiktok_provider_contract():
    from social_data.providers.tiktok.provider import TikTokProvider
    from social_data.services.refresh_service import Credentials

    calls = []
    p = TikTokProvider("ck", "cs", http=httpx.Client(transport=tiktok_transport(calls)), redirect_uri="http://x/cb")
    url, state = p.authorize_url()
    assert "client_key=ck" in url and "user.info.stats" in url and f"state={state}" in url
    tokens = p.exchange_code("CODE")
    creds = Credentials(tokens.access_token)
    acc = p.resolve_account(TT, credentials=creds)
    assert acc.external_id == "OPEN1" and acc.handle == "creator_one"
    result = p.fetch(acc, limit=15, credentials=creds)
    assert result.account.followers == 12345
    assert len(result.videos) == 15 and result.videos[0].views == 100
    assert sum(1 for c in calls if c[1] == "/v2/video/list/") == 1  # 15 < page size 20
    with pytest.raises(errors.AuthorizationRequired):
        p.get_account_statistics(acc, credentials=None)
    with pytest.raises(errors.AuthorizationExpired):
        p.get_account_statistics(acc, credentials=Credentials("bad"))
    with pytest.raises(errors.ProviderError):
        p.resolve_account("https://www.tiktok.com/@someone_else", credentials=creds)
    with pytest.raises(errors.ProviderNotConfigured):
        TikTokProvider("", "")


# --- contract tests: YouTube Data API -------------------------------------------------
def youtube_transport(quota=False, hidden=False):
    def handler(request: httpx.Request):
        if quota:
            return httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})
        p = request.url.path.rsplit("/", 1)[-1]
        q = request.url.params
        if p == "channels":
            assert q.get("forHandle") == "@chan" or q.get("id") == "UC" + "x" * 22
            return httpx.Response(200, json={"items": [{"id": "UC" + "x" * 22, "snippet": {"title": "Chan", "customUrl": "@chan"},
                                                        "statistics": {"subscriberCount": "777", "hiddenSubscriberCount": hidden},
                                                        "contentDetails": {"relatedPlaylists": {"uploads": "UUxx"}}}]})
        if p == "playlistItems":
            return httpx.Response(200, json={"items": [{"contentDetails": {"videoId": f"vid{i:08d}"}} for i in range(30)]})
        if p == "videos":
            ids = q.get("id").split(",")
            items = [{"id": v, "statistics": {"viewCount": str(1000 + i)}, "snippet": {"publishedAt": "2026-11-01T10:00:00Z"},
                      "contentDetails": {"duration": "PT45S" if i % 2 == 0 else "PT12M3S"}} for i, v in enumerate(ids)]
            return httpx.Response(200, json={"items": items})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def test_youtube_provider_contract_and_shorts_heuristic():
    from social_data.providers.youtube.provider import YouTubeProvider, parse_duration

    assert parse_duration("PT45S") == 45 and parse_duration("PT1M30S") == 90 and parse_duration("PT3M") == 180
    assert parse_duration("P1DT1H") == 90000 and parse_duration("bad") is None
    p = YouTubeProvider("KEY", http=httpx.Client(transport=youtube_transport()))
    acc = p.resolve_account("https://www.youtube.com/@chan")
    assert acc.external_id == "UC" + "x" * 22 and acc.handle == "chan"
    result = p.fetch(acc, limit=15)
    assert result.account.followers == 777
    assert len(result.videos) == 15 and all(v.is_short_heuristic for v in result.videos)  # long videos skipped
    assert result.videos[0].views == 1000 and result.videos[1].views == 1002
    with pytest.raises(errors.ProviderRateLimited):
        YouTubeProvider("KEY", http=httpx.Client(transport=youtube_transport(quota=True))).resolve_account("https://www.youtube.com/@chan")
    with pytest.raises(errors.ProviderError):
        YouTubeProvider("KEY", http=httpx.Client(transport=youtube_transport(hidden=True))).get_account_statistics(acc)
    v = p.get_video_statistics("https://www.youtube.com/shorts/abcdefghijk")
    assert v is not None


# --- OAuth flow (TikTok, owner authorization) -------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_tiktok_oauth_flow_verifies_ownership_and_encrypts_tokens(api, seller, settings, monkeypatch):
    from social_data.providers.tiktok import provider as tt

    settings.TIKTOK_CLIENT_KEY, settings.TIKTOK_CLIENT_SECRET = "ck", "cs"
    calls = []
    real_init = tt.TikTokProvider.__init__
    monkeypatch.setattr(tt.TikTokProvider, "__init__", lambda self, k, s, http=None, redirect_uri="":
                        real_init(self, k, s, http=httpx.Client(transport=tiktok_transport(calls)), redirect_uri="http://x/cb"))
    settings.SOCIAL_PROVIDER_MODE = "official"
    api.force_login(seller)
    start = api.get("/api/v1/social-accounts/oauth/tiktok/start").json()
    state = start["authorize_url"].split("state=")[1]
    bad = api.post("/api/v1/social-accounts/oauth/tiktok/callback", {"code": "C", "state": "forged"}, format="json")
    assert bad.json()["error"]["code"] == "oauth_state_mismatch"
    api.get("/api/v1/social-accounts/oauth/tiktok/start")
    state = api.get("/api/v1/social-accounts/oauth/tiktok/start").json()["authorize_url"].split("state=")[1]
    r = api.post("/api/v1/social-accounts/oauth/tiktok/callback", {"code": "C", "state": state}, format="json")
    assert r.status_code == 201, r.content
    acc = SocialAccount.objects.get(pk=r.json()["id"])
    assert acc.ownership_verified and acc.external_id == "OPEN1"
    assert acc.connection.access_token_enc and "act.1" not in acc.connection.access_token_enc
    assert acc.current_statistics.followers == 12345 and acc.current_statistics.videos_in_sample == 15
    # without OAuth, adding TikTok by URL in official mode asks to authorize
    r = add(api, url="https://www.tiktok.com/@another_user")
    assert r.json()["error"]["code"] == "oauth_required"

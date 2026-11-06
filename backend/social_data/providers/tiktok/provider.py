"""TikTok Display API adapter (docs/SOCIAL_DATA.md §2.1).

Only the official API with the account OWNER's OAuth token (Login Kit). Without the owner's
authorization TikTok data is not fetched at all — no scraping, no foreign sessions.
Scopes: user.info.basic, user.info.profile, user.info.stats (follower_count), video.list (view_count).
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from django.conf import settings

from social_data.core import errors
from social_data.core.provider import SocialDataProvider
from social_data.core.types import AccountStats, Availability, ResolvedAccount, VideoStats
from social_data.core.url_parser import detect_platform

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,user.info.profile,user.info.stats,video.list"
VIDEO_FIELDS = "id,create_time,share_url,view_count,like_count,comment_count,duration"
MAX_PAGE = 20  # TikTok video.list max_count


@dataclass
class TikTokTokens:
    access_token: str
    refresh_token: str
    open_id: str
    expires_at: datetime
    scope: str


class TikTokProvider(SocialDataProvider):
    platform = "tiktok"
    source = "official_api"

    def __init__(self, client_key: str, client_secret: str, http: httpx.Client | None = None, redirect_uri: str = ""):
        if not client_key or not client_secret:
            raise errors.ProviderNotConfigured("TikTok app credentials are not configured")
        self.client_key = client_key
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri or f"{settings.FRONTEND_URL}/account/accounts/oauth/tiktok"
        self.http = http or httpx.Client(timeout=15.0)

    @classmethod
    def from_settings(cls) -> "TikTokProvider":
        return cls(settings.TIKTOK_CLIENT_KEY, settings.TIKTOK_CLIENT_SECRET)

    # --- OAuth (Login Kit) ---------------------------------------------------
    def authorize_url(self, state: str | None = None) -> tuple[str, str]:
        state = state or secrets.token_urlsafe(24)
        q = {"client_key": self.client_key, "scope": SCOPES, "response_type": "code",
             "redirect_uri": self.redirect_uri, "state": state}
        return f"{AUTHORIZE_URL}?{urlencode(q)}", state

    def exchange_code(self, code: str) -> TikTokTokens:
        return self._token({"code": code, "grant_type": "authorization_code", "redirect_uri": self.redirect_uri})

    def refresh(self, refresh_token: str) -> TikTokTokens:
        return self._token({"refresh_token": refresh_token, "grant_type": "refresh_token"})

    def _token(self, extra: dict) -> TikTokTokens:
        data = {"client_key": self.client_key, "client_secret": self.client_secret, **extra}
        resp = self._call("POST", f"{API}/oauth/token/", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        body = resp.json()
        if "access_token" not in body:
            raise errors.AuthorizationExpired(body.get("error_description") or "token exchange failed")
        return TikTokTokens(
            access_token=body["access_token"], refresh_token=body.get("refresh_token", ""), open_id=body.get("open_id", ""),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(body.get("expires_in", 0))), scope=body.get("scope", ""),
        )

    # --- HTTP ---------------------------------------------------------------
    def _call(self, method: str, url: str, **kw) -> httpx.Response:
        try:
            resp = self.http.request(method, url, **kw)
        except httpx.HTTPError as e:
            raise errors.ProviderUnavailable(str(e)) from e
        if resp.status_code == 429:
            raise errors.ProviderRateLimited("tiktok 429")
        if resp.status_code == 401:
            raise errors.AuthorizationExpired("tiktok 401")
        if resp.status_code >= 500:
            raise errors.ProviderUnavailable(f"tiktok {resp.status_code}")
        return resp

    def _api(self, method: str, path: str, token: str, *, fields: str, json: dict | None = None) -> dict:
        resp = self._call(method, f"{API}{path}", params={"fields": fields}, json=json,
                          headers={"Authorization": f"Bearer {token}"})
        body = resp.json()
        err = (body.get("error") or {}).get("code", "ok")
        if err == "ok":
            return body.get("data") or {}
        if err in ("access_token_invalid", "scope_not_authorized"):
            raise errors.AuthorizationExpired(err)
        if err == "rate_limit_exceeded":
            raise errors.ProviderRateLimited(err)
        raise errors.ProviderError(err)

    @staticmethod
    def _token_of(credentials) -> str:
        if not credentials or not getattr(credentials, "access_token", None):
            raise errors.AuthorizationRequired("TikTok requires owner authorization")
        return credentials.access_token

    # --- SocialDataProvider ---------------------------------------------------
    def validate_profile_url(self, url):
        platform, handle = detect_platform(url)
        if platform != "tiktok":
            raise errors.InvalidProfileUrl("not tiktok")
        return handle

    def resolve_account(self, url="", *, credentials=None):
        token = self._token_of(credentials)
        user = self._api("GET", "/user/info/", token, fields="open_id,display_name,username,profile_deep_link")["user"]
        handle = user.get("username") or ""
        if url:
            expected = self.validate_profile_url(url)
            if handle and expected.lower() != handle.lower():
                raise errors.ProviderError("profile url does not match authorized account",
                                           user_message="Ссылка не совпадает с аккаунтом, в который выполнен вход")
        return ResolvedAccount(platform="tiktok", external_id=user["open_id"], handle=handle,
                               profile_url=url or f"https://www.tiktok.com/@{handle}", title=user.get("display_name") or handle)

    def get_account_statistics(self, account, *, credentials=None):
        token = self._token_of(credentials)
        user = self._api("GET", "/user/info/", token, fields="open_id,follower_count")["user"]
        return AccountStats(followers=int(user.get("follower_count") or 0))

    def get_recent_videos(self, account, *, limit, credentials=None):
        token = self._token_of(credentials)
        videos: list[VideoStats] = []
        cursor = None
        for _ in range(5):  # bounded pagination
            payload = {"max_count": min(MAX_PAGE, limit - len(videos))}
            if cursor is not None:
                payload["cursor"] = cursor
            data = self._api("POST", "/video/list/", token, fields=VIDEO_FIELDS, json=payload)
            for v in data.get("videos", []):
                videos.append(self._video(v))
                if len(videos) >= limit:
                    return videos
            if not data.get("has_more"):
                break
            cursor = data.get("cursor")
        return videos

    @staticmethod
    def _video(v: dict) -> VideoStats:
        ts = v.get("create_time")
        return VideoStats(
            external_id=str(v["id"]), url=v.get("share_url") or f"https://www.tiktok.com/video/{v['id']}",
            views=int(v.get("view_count") or 0), likes=v.get("like_count"), comments=v.get("comment_count"),
            duration_s=v.get("duration"), published_at=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None,
        )

    def get_video_statistics(self, video_url, *, credentials=None):
        token = self._token_of(credentials)
        vid = video_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
        if not vid.isdigit():
            raise errors.InvalidProfileUrl("bad tiktok video url")
        data = self._api("POST", "/video/query/", token, fields=VIDEO_FIELDS, json={"filters": {"video_ids": [vid]}})
        items = data.get("videos") or []
        return self._video(items[0]) if items else None

    def check_data_availability(self, account, *, credentials=None):
        if not credentials:
            return Availability(False, "authorization_required")
        try:
            self.get_account_statistics(account, credentials=credentials)
        except errors.ProviderError as e:
            return Availability(False, e.code)
        return Availability(True)

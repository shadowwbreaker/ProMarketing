"""YouTube Data API v3 adapter (docs/SOCIAL_DATA.md §2.3).

Public channel/video statistics via API key. Shorts have no official API flag: we use the
duration heuristic (<= 180 s) and mark `is_short_heuristic`. The average of recent videos is a
derived metric — it is NOT shown to third parties until YOUTUBE_DERIVED_METRICS_APPROVED (D-016).
Quota per refresh: channels.list (1) + playlistItems.list (1) + videos.list (1) = 3 units.
"""
from __future__ import annotations

import re
from datetime import datetime

import httpx
from django.conf import settings

from social_data.core import errors
from social_data.core.provider import SocialDataProvider
from social_data.core.types import AccountStats, Availability, ResolvedAccount, VideoStats
from social_data.core.url_parser import detect_platform

API = "https://www.googleapis.com/youtube/v3"
SHORTS_MAX_SECONDS = 180
_DURATION = re.compile(r"^P(?:(?P<d>\d+)D)?T?(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?$")
_VIDEO_ID = re.compile(r"(?:youtube\.com/(?:shorts/|watch\?v=)|youtu\.be/)([A-Za-z0-9_-]{11})")


def parse_duration(iso: str) -> int | None:
    m = _DURATION.match(iso or "")
    if not m:
        return None
    p = {k: int(v or 0) for k, v in m.groupdict().items()}
    return p["d"] * 86400 + p["h"] * 3600 + p["m"] * 60 + p["s"]


class YouTubeProvider(SocialDataProvider):
    platform = "youtube"
    source = "official_api"

    def __init__(self, api_key: str, http: httpx.Client | None = None):
        if not api_key:
            raise errors.ProviderNotConfigured("YOUTUBE_API_KEY is not configured")
        self.api_key = api_key
        self.http = http or httpx.Client(timeout=15.0)

    @classmethod
    def from_settings(cls) -> "YouTubeProvider":
        return cls(settings.YOUTUBE_API_KEY)

    def _get(self, resource: str, **params) -> dict:
        try:
            resp = self.http.get(f"{API}/{resource}", params={**params, "key": self.api_key})
        except httpx.HTTPError as e:
            raise errors.ProviderUnavailable(str(e)) from e
        if resp.status_code == 403:
            reason = ""
            try:
                reason = resp.json()["error"]["errors"][0]["reason"]
            except (KeyError, IndexError, ValueError):
                pass
            if reason in ("quotaExceeded", "rateLimitExceeded", "dailyLimitExceeded"):
                raise errors.ProviderRateLimited(reason)
            raise errors.ProviderError(f"youtube 403 {reason}")
        if resp.status_code == 404:
            raise errors.AccountNotFound("youtube 404")
        if resp.status_code >= 500:
            raise errors.ProviderUnavailable(f"youtube {resp.status_code}")
        if resp.status_code >= 400:
            raise errors.ProviderError(f"youtube {resp.status_code}")
        return resp.json()

    def validate_profile_url(self, url):
        platform, ident = detect_platform(url)
        if platform != "youtube":
            raise errors.InvalidProfileUrl("not youtube")
        return ident

    def _channel(self, ident: str) -> dict:
        params = {"part": "snippet,statistics,contentDetails"}
        if ident.startswith("UC") and len(ident) == 24:
            params["id"] = ident
        else:
            params["forHandle"] = f"@{ident.lstrip('@')}"
        items = self._get("channels", **params).get("items") or []
        if not items:
            raise errors.AccountNotFound("channel not found")
        return items[0]

    def resolve_account(self, url, *, credentials=None):
        ident = self.validate_profile_url(url)
        ch = self._channel(ident)
        handle = (ch["snippet"].get("customUrl") or ident).lstrip("@")
        return ResolvedAccount(platform="youtube", external_id=ch["id"], handle=handle, profile_url=url,
                               title=ch["snippet"].get("title", handle))

    def profile_contains(self, account, code):
        """Channel description via channels.list (official API, one call per user click)."""
        ch = self._channel(account.external_id)
        return code in (ch.get("snippet", {}).get("description") or "")

    def get_account_statistics(self, account, *, credentials=None):
        ch = self._channel(account.external_id)
        st = ch.get("statistics", {})
        if st.get("hiddenSubscriberCount"):
            raise errors.ProviderError("subscriber count hidden", user_message="Владелец канала скрыл число подписчиков")
        return AccountStats(followers=int(st.get("subscriberCount") or 0))

    def get_recent_videos(self, account, *, limit, credentials=None):
        ch = self._channel(account.external_id)
        uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        items = self._get("playlistItems", part="contentDetails", playlistId=uploads, maxResults=50).get("items") or []
        ids = [i["contentDetails"]["videoId"] for i in items]
        if not ids:
            return []
        videos = self._get("videos", part="statistics,contentDetails,snippet", id=",".join(ids), maxResults=50).get("items") or []
        by_id = {v["id"]: v for v in videos}
        result = []
        for vid in ids:  # keep upload order (newest first)
            v = by_id.get(vid)
            if not v:
                continue
            vs = self._video(v)
            if vs.is_short_heuristic:
                result.append(vs)
            if len(result) >= limit:
                break
        return result

    @staticmethod
    def _video(v: dict) -> VideoStats:
        dur = parse_duration(v.get("contentDetails", {}).get("duration", ""))
        published = v.get("snippet", {}).get("publishedAt")
        st = v.get("statistics", {})
        return VideoStats(
            external_id=v["id"], url=f"https://www.youtube.com/shorts/{v['id']}", views=int(st.get("viewCount") or 0),
            likes=int(st["likeCount"]) if "likeCount" in st else None,
            comments=int(st["commentCount"]) if "commentCount" in st else None, duration_s=dur,
            published_at=datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None,
            is_short_heuristic=dur is not None and dur <= SHORTS_MAX_SECONDS,
        )

    def get_video_statistics(self, video_url, *, credentials=None):
        m = _VIDEO_ID.search(video_url or "")
        if not m:
            raise errors.InvalidProfileUrl("bad youtube video url")
        items = self._get("videos", part="statistics,contentDetails,snippet", id=m.group(1)).get("items") or []
        return self._video(items[0]) if items else None

    def check_data_availability(self, account, *, credentials=None):
        try:
            self._channel(account.external_id)
        except errors.ProviderError as e:
            return Availability(False, e.code)
        return Availability(True)

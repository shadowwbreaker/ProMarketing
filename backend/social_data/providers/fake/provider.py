"""Deterministic fake provider for dev and tests ONLY. Forbidden in production (config/settings/prod.py).

Behaviour is driven by the handle so tests can simulate platform responses:
  *_unavailable -> ProviderUnavailable, *_ratelimit -> ProviderRateLimited,
  *_notpro -> NotProfessionalAccount, *_notmine -> ownership code not found, *_fewvideos -> 3 videos, *_novideos -> 0 videos.
"""
import hashlib
from datetime import datetime, timedelta, timezone

from social_data.core import errors
from social_data.core.provider import SocialDataProvider
from social_data.core.types import AccountStats, Availability, ResolvedAccount, VideoStats
from social_data.core.url_parser import detect_platform


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


class FakeProvider(SocialDataProvider):
    source = "fake"

    def __init__(self, platform: str):
        self.platform = platform
        self.calls: list[str] = []

    def validate_profile_url(self, url):
        platform, handle = detect_platform(url)
        if platform != self.platform:
            raise errors.InvalidProfileUrl("platform mismatch")
        return handle

    def _raise_for(self, handle: str):
        if handle.endswith("_unavailable"):
            raise errors.ProviderUnavailable("fake unavailable")
        if handle.endswith("_ratelimit"):
            raise errors.ProviderRateLimited("fake ratelimit")
        if handle.endswith("_notpro"):
            raise errors.NotProfessionalAccount("fake notpro")
        if handle.endswith("_missing"):
            raise errors.AccountNotFound("fake missing")

    def resolve_account(self, url, *, credentials=None):
        handle = self.validate_profile_url(url)
        self.calls.append(f"resolve:{handle}")
        self._raise_for(handle)
        return ResolvedAccount(platform=self.platform, external_id=f"fake-{self.platform}-{handle.lower()}",
                               handle=handle, profile_url=url, title=handle)

    def get_account_statistics(self, account, *, credentials=None):
        self.calls.append(f"stats:{account.handle}")
        self._raise_for(account.handle)
        return AccountStats(followers=10_000 + _seed(account.handle) % 990_000)

    def get_recent_videos(self, account, *, limit, credentials=None):
        self.calls.append(f"videos:{account.handle}")
        self._raise_for(account.handle)
        count = 0 if account.handle.endswith("_novideos") else 3 if account.handle.endswith("_fewvideos") else 20
        base = datetime(2026, 11, 1, tzinfo=timezone.utc)
        videos = []
        for i in range(min(count, limit)):
            vid = f"{account.handle}-v{i}"
            videos.append(VideoStats(external_id=vid, url=f"https://example.invalid/{self.platform}/{vid}",
                                     views=1_000 * (i + 1) + _seed(vid) % 1000, published_at=base - timedelta(days=i),
                                     duration_s=30, is_short_heuristic=self.platform == "youtube"))
        return videos

    def profile_contains(self, account, code):
        """Dev/test: handles ending with _notmine never contain the code; everything else does."""
        self.calls.append(f"ownership:{account.handle}")
        self._raise_for(account.handle)
        return not account.handle.endswith("_notmine")

    def get_video_statistics(self, video_url, *, credentials=None):
        self.calls.append(f"video:{video_url}")
        if "deleted" in video_url:
            return None
        return VideoStats(external_id=video_url.rsplit("/", 1)[-1], url=video_url, views=1000)

    def check_data_availability(self, account, *, credentials=None):
        if account.handle.endswith("_unavailable") or account.handle.endswith("_missing"):
            return Availability(False, "unavailable")
        return Availability(True)

"""Manual statistics entered by the account owner. Always MANUAL, never VERIFIED (roadmap 3.7)."""
from social_data.core import errors
from social_data.core.provider import SocialDataProvider
from social_data.core.types import AccountStats, Availability, ResolvedAccount
from social_data.core.url_parser import detect_platform


class ManualProvider(SocialDataProvider):
    source = "manual"

    def __init__(self, platform: str):
        self.platform = platform

    def validate_profile_url(self, url):
        platform, handle = detect_platform(url)
        if platform != self.platform:
            raise errors.InvalidProfileUrl("platform mismatch")
        return handle

    def resolve_account(self, url, *, credentials=None):
        handle = self.validate_profile_url(url)
        return ResolvedAccount(platform=self.platform, external_id=f"manual-{self.platform}-{handle.lower()}",
                               handle=handle, profile_url=url, title=handle)

    def get_account_statistics(self, account, *, credentials=None):
        raise errors.ProviderNotConfigured("manual provider does not fetch")

    def get_recent_videos(self, account, *, limit, credentials=None):
        return []

    def get_video_statistics(self, video_url, *, credentials=None):
        return None

    def check_data_availability(self, account, *, credentials=None):
        return Availability(False, "manual")

    def build_manual(self, followers: int, video_views: list[int]) -> tuple[AccountStats, list[int]]:
        if followers < 0 or any(v < 0 for v in video_views):
            raise ValueError("negative values")
        return AccountStats(followers=followers), video_views

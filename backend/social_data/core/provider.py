"""Social Data Provider interface (roadmap 3.6).

Each platform has its own adapter. Providers know nothing about each other or about
storage/limits — that lives in social_data.services. Providers must only use
allowed methods (official APIs / licensed vendors); no scraping, no CAPTCHA or
anti-bot bypass, no foreign cookies or sessions (roadmap 3.7).
"""
from abc import ABC, abstractmethod

from .types import AccountStats, Availability, FetchResult, ResolvedAccount, VideoStats


class SocialDataProvider(ABC):
    platform: str
    source: str = "official_api"

    @abstractmethod
    def validate_profile_url(self, url: str) -> str:
        """Return normalized handle/identifier or raise InvalidProfileUrl."""

    @abstractmethod
    def resolve_account(self, url: str, *, credentials=None) -> ResolvedAccount: ...

    @abstractmethod
    def get_account_statistics(self, account: ResolvedAccount, *, credentials=None) -> AccountStats: ...

    @abstractmethod
    def get_recent_videos(self, account: ResolvedAccount, *, limit: int, credentials=None) -> list[VideoStats]:
        """Most recent eligible published videos, newest first, at most `limit`."""

    @abstractmethod
    def get_video_statistics(self, video_url: str, *, credentials=None) -> VideoStats | None:
        """One-off lookup of a single video (used by publication checks, D-010)."""

    def profile_contains(self, account: ResolvedAccount, code: str) -> bool:
        """Ownership check: does the public profile description contain `code`? (D-020)

        Only platforms whose official API exposes the description support it; others raise.
        """
        from .errors import ProviderError

        raise ProviderError("ownership check not supported",
                            user_message="Для этой платформы владение подтверждается входом через платформу")

    def normalize_response(self, raw: dict) -> dict:
        return raw

    @abstractmethod
    def check_data_availability(self, account: ResolvedAccount, *, credentials=None) -> Availability: ...

    def fetch(self, account: ResolvedAccount, *, limit: int, credentials=None) -> FetchResult:
        """One full statistics cycle. Called exactly once per StatsRefreshJob."""
        stats = self.get_account_statistics(account, credentials=credentials)
        videos = self.get_recent_videos(account, limit=limit, credentials=credentials)
        return FetchResult(account=stats, videos=videos[:limit], source=self.source, verified=self.source == "official_api")

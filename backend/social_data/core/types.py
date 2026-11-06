from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ResolvedAccount:
    platform: str
    external_id: str
    handle: str
    profile_url: str
    title: str = ""
    is_professional: bool = True


@dataclass(frozen=True)
class AccountStats:
    followers: int


@dataclass(frozen=True)
class VideoStats:
    external_id: str
    url: str
    views: int
    published_at: datetime | None = None
    likes: int | None = None
    comments: int | None = None
    duration_s: int | None = None
    is_short_heuristic: bool = False


@dataclass(frozen=True)
class Availability:
    available: bool
    reason: str = ""


@dataclass
class FetchResult:
    account: AccountStats
    videos: list[VideoStats] = field(default_factory=list)
    source: str = "official_api"
    verified: bool = True

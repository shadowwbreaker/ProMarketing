from django.conf import settings

from .errors import PlatformDisabled, ProviderNotConfigured
from .provider import SocialDataProvider

_override: dict[str, SocialDataProvider] = {}


def platform_enabled(platform: str) -> bool:
    return {
        "tiktok": settings.PLATFORM_TIKTOK_ENABLED,
        "instagram": settings.PLATFORM_INSTAGRAM_ENABLED,  # D-013: disabled for RF market
        "youtube": settings.PLATFORM_YOUTUBE_ENABLED,
    }.get(platform, False)


def provider_mode(platform: str) -> str:
    """'official' or 'fake' for one platform.

    SOCIAL_PROVIDER_MODE=auto (dev default): a platform uses its real API as soon as its keys are configured
    (YOUTUBE_API_KEY; TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET), otherwise demo data.
    """
    mode = settings.SOCIAL_PROVIDER_MODE
    if mode != "auto":
        return mode
    configured = {
        "youtube": bool(settings.YOUTUBE_API_KEY),
        "tiktok": bool(settings.TIKTOK_CLIENT_KEY and settings.TIKTOK_CLIENT_SECRET),
    }.get(platform, False)
    return "official" if configured else "fake"


def get_provider(platform: str) -> SocialDataProvider:
    if not platform_enabled(platform):
        raise PlatformDisabled(platform)
    if platform in _override:
        return _override[platform]
    mode = provider_mode(platform)
    if mode == "fake":
        from social_data.providers.fake.provider import FakeProvider

        return FakeProvider(platform)
    if mode == "official":
        if platform == "tiktok":
            from social_data.providers.tiktok.provider import TikTokProvider

            return TikTokProvider.from_settings()
        if platform == "youtube":
            from social_data.providers.youtube.provider import YouTubeProvider

            return YouTubeProvider.from_settings()
        if platform == "instagram":
            from social_data.providers.instagram.provider import InstagramProvider

            return InstagramProvider.from_settings()
    raise ProviderNotConfigured(f"{platform}/{mode}")


def set_provider_override(platform: str, provider: SocialDataProvider | None):
    """Test hook."""
    if provider is None:
        _override.pop(platform, None)
    else:
        _override[platform] = provider

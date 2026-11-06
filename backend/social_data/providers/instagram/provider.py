"""Instagram adapter — [!] BLOCKED for the RF market (D-013, D-007).

Advertising on Meta resources is prohibited in Russia since 2025-09-01, so the platform is disabled
by PLATFORM_INSTAGRAM_ENABLED=false and this adapter is intentionally not implemented. If another
market is opened, implement via Instagram API with Instagram Login (professional accounts only).
"""
from social_data.core import errors


class InstagramProvider:
    platform = "instagram"

    @classmethod
    def from_settings(cls):
        raise errors.ProviderNotConfigured("Instagram adapter is blocked by decision D-013")

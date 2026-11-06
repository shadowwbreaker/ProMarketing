from django.conf import settings


def platform_fee(amount_minor: int, fee_bps: int | None = None) -> int:
    """Platform fee in minor units, rounded down in favour of the seller (D-015)."""
    if amount_minor < 0:
        raise ValueError("amount must be non-negative")
    bps = settings.PLATFORM_FEE_BPS if fee_bps is None else fee_bps
    if not 0 <= bps <= 10_000:
        raise ValueError("fee bps out of range")
    return amount_minor * bps // 10_000


def split_amount(amount_minor: int, fee_bps: int | None = None) -> tuple[int, int]:
    """Return (platform_fee, seller_amount) for a price paid by buyer."""
    fee = platform_fee(amount_minor, fee_bps)
    return fee, amount_minor - fee

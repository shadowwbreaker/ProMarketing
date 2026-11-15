from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import PaymentProvider

_instance: PaymentProvider | None = None


def get_payment_provider() -> PaymentProvider:
    global _instance
    if _instance is not None:
        return _instance
    if settings.PAYMENT_PROVIDER == "mock":
        if settings.BETA_MODE:
            from .beta import BetaPaymentProvider

            _instance = BetaPaymentProvider()
        else:
            from .mock import MockPaymentProvider

            _instance = MockPaymentProvider()
        return _instance
    raise ImproperlyConfigured(f"Payment provider '{settings.PAYMENT_PROVIDER}' is not implemented (Q-03)")


def set_payment_provider(provider: PaymentProvider | None):
    """Test hook."""
    global _instance
    _instance = provider

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import FIELD_ENCRYPTION_KEY, PAYMENT_PROVIDER, SECRET_KEY, SOCIAL_PROVIDER_MODE, env

ENV = "production"
DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if SECRET_KEY.startswith("dev-"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production")
if PAYMENT_PROVIDER == "mock":
    raise ImproperlyConfigured("Mock payment provider is forbidden in production (D-008)")
if SOCIAL_PROVIDER_MODE == "fake":
    raise ImproperlyConfigured("Fake social providers are forbidden in production")
if not FIELD_ENCRYPTION_KEY:
    raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY must be set in production")

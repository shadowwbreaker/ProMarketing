"""Production settings. Refuses to start with dev/mock/fake configuration (D-008).
Production deployment itself requires explicit permission from the project owner."""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import FIELD_ENCRYPTION_KEY, MIDDLEWARE, PAYMENT_PROVIDER, SECRET_KEY, SOCIAL_PROVIDER_MODE, env

ENV = "production"
DEBUG = False

# --- HTTPS / cookies ----------------------------------------------------------------
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default=None)  # e.g. ".promarketing.ru" when API is api.promarketing.ru
CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN", default=None)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)  # enable only after the domain is ready for preload
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/"]  # load balancer probes over plain HTTP

# --- static & media -----------------------------------------------------------------
MIDDLEWARE = [MIDDLEWARE[0], MIDDLEWARE[1], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[2:]]
S3_BUCKET = env("S3_BUCKET", default="")
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": S3_BUCKET,
            "endpoint_url": env("S3_ENDPOINT_URL", default=None),  # MinIO / Yandex Object Storage / Selectel
            "region_name": env("S3_REGION", default=None),
            "access_key": env("S3_ACCESS_KEY", default=None),
            "secret_key": env("S3_SECRET_KEY", default=None),
            "default_acl": "private",
            "querystring_auth": True,
            "querystring_expire": 300,
            "file_overwrite": False,
        },
    },
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# drf-spectacular falls back to generic schemas for plain APIViews; documentation-only warning.
SILENCED_SYSTEM_CHECKS = ["drf_spectacular.W001", "drf_spectacular.W002"]

STAFF_2FA_REQUIRED = env.bool("STAFF_2FA_REQUIRED", default=True)

# --- refuse unsafe configuration -------------------------------------------------------
_errors = []
if SECRET_KEY.startswith("dev-") or len(SECRET_KEY) < 40:
    _errors.append("DJANGO_SECRET_KEY must be a strong secret (>= 40 chars)")
if PAYMENT_PROVIDER == "mock":
    _errors.append("Mock payment provider is forbidden in production (D-008)")
if SOCIAL_PROVIDER_MODE == "fake":
    _errors.append("Fake social providers are forbidden in production")
if env.bool("DEV_AUTO_VERIFY_EMAIL", default=False):
    _errors.append("DEV_AUTO_VERIFY_EMAIL must be false in production")
REST_FRAMEWORK["NUM_PROXIES"] = env.int("NUM_PROXIES", default=1)  # noqa: F405 — Caddy in front (infra/Caddyfile)
if not FIELD_ENCRYPTION_KEY:
    _errors.append("FIELD_ENCRYPTION_KEY must be set in production")
if not S3_BUCKET:
    _errors.append("S3_BUCKET must be set in production (attachments/evidence storage)")
if env("EMAIL_BACKEND", default="").endswith("console.EmailBackend"):
    _errors.append("Console email backend is forbidden in production")
if _errors:
    raise ImproperlyConfigured("; ".join(_errors))

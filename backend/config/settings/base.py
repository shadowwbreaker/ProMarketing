"""Base settings shared by all environments.

All environment-specific values come from environment variables (see .env.example).
Secrets are never hard-coded here.
"""
from datetime import timedelta  # noqa: F401  (used by environment overrides)
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# A local .env is optional and never created by tooling; values in the real
# environment take precedence.
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

ENV = env("APP_ENV", default="dev")
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "common",
    "accounts",
    "audit",
    "files",
    "social_data",
    "catalog",
    "orders",
    "payments",
    "chats",
    "notifications",
    "support",
    "reviews",
    "staff",
    "antifraud",
    "insights",
]

MIDDLEWARE = [
    "common.middleware.RequestIdMiddleware",
    "common.middleware.SecurityHeadersMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.LastSeenMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://promarketing:promarketing@localhost:5432/promarketing",
    )
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "UTC"  # storage in UTC; display timezone is a frontend concern (Europe/Moscow by default)
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))
ATTACHMENT_MAX_SIZE = env.int("ATTACHMENT_MAX_SIZE", default=20 * 1024 * 1024)
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Sessions / CSRF -------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=60 * 60 * 24 * 14)
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:3000"])
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])
CORS_ALLOW_CREDENTIALS = True

# --- DRF -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        "auth": env("THROTTLE_AUTH", default="10/min"),
        "stats_refresh": env("THROTTLE_STATS_REFRESH", default="10/hour"),
        "chat": env("THROTTLE_CHAT", default="30/min"),
        "dispute_open": env("THROTTLE_DISPUTE_OPEN", default="10/day"),
        "ticket": env("THROTTLE_TICKET", default="10/day"),
        "review": env("THROTTLE_REVIEW", default="30/day"),
    },
}
SPECTACULAR_SETTINGS = {
    "TITLE": "ProMarketing API",
    "DESCRIPTION": "Маркетплейс рекламы в TikTok, Instagram Reels и YouTube Shorts",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Cache / Celery --------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = None
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
# Periodic tasks: ONLY internal timers and data-retention cleanup (DECISIONS D-004).
# Never add a periodic task that calls social platforms. Enforced by tests.
CELERY_BEAT_SCHEDULE = {
    # Deletion only (YouTube API data retention, D-016) — does not fetch anything.
    "purge-expired-youtube-data": {"task": "social_data.tasks.purge_expired_youtube_data", "schedule": 60 * 60 * 24},
    # Internal order/payment timers (D-004). They never poll social platforms; window_end creates at most
    # one event-driven publication check per order item (D-010).
    "orders-expire-unaccepted": {"task": "orders.tasks.expire_unaccepted", "schedule": 300},
    "orders-confirmation-windows": {"task": "orders.tasks.process_confirmation_windows", "schedule": 600},
    "orders-missed-deadlines": {"task": "orders.tasks.notify_missed_publish_deadlines", "schedule": 3600},
    "orders-deadlines-soon": {"task": "orders.tasks.notify_deadlines_soon", "schedule": 3600},
    "payments-release-payouts": {"task": "payments.tasks.release_payouts", "schedule": 600},
    "support-dispute-timeouts": {"task": "support.tasks.process_dispute_timeouts", "schedule": 900},
    "support-close-appeal-windows": {"task": "support.tasks.close_expired_appeal_windows", "schedule": 3600},
    "accounts-expire-sanctions": {"task": "accounts.tasks.expire_sanctions", "schedule": 900},
    # D-018: pre-planned result checkpoints only (buyer opt-in, at most 3 per order item, never rescheduled).
    "insights-due-metrics": {"task": "insights.tasks.collect_due_metrics", "schedule": 900},
}

# --- Email -----------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@promarketing.local")
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# --- Business settings (all configurable) ----------------------------------
DEFAULT_CURRENCY = env("DEFAULT_CURRENCY", default="RUB")  # D-013
PLATFORM_FEE_BPS = env.int("PLATFORM_FEE_BPS", default=500)  # D-015: 5%
PLATFORM_FEE_PAYER = env("PLATFORM_FEE_PAYER", default="seller")  # D-015 assumption
PAYOUT_HOLD_HOURS = env.int("PAYOUT_HOLD_HOURS", default=48)  # D-014
STATS_REFRESH_INTERVAL_HOURS = env.int("STATS_REFRESH_INTERVAL_HOURS", default=24)
STATS_SAMPLE_SIZE = env.int("STATS_SAMPLE_SIZE", default=15)
STATS_STALE_AFTER_DAYS = env.int("STATS_STALE_AFTER_DAYS", default=30)
SELLER_ACCEPT_TIMEOUT_HOURS = env.int("SELLER_ACCEPT_TIMEOUT_HOURS", default=24)
BUYER_CONFIRM_WINDOW_HOURS = env.int("BUYER_CONFIRM_WINDOW_HOURS", default=72)
DISPUTE_RESPONSE_HOURS = env.int("DISPUTE_RESPONSE_HOURS", default=48)
BUYER_PUBLICATION_CHECKS_LIMIT = env.int("BUYER_PUBLICATION_CHECKS_LIMIT", default=3)
STAFF_2FA_REQUIRED = env.bool("STAFF_2FA_REQUIRED", default=False)  # forced on in production
RESULTS_REPORTS_ENABLED = env.bool("RESULTS_REPORTS_ENABLED", default=True)  # D-018: buyer opt-in, 3 checks max

# Platform feature flags (D-013, D-016)
PLATFORM_TIKTOK_ENABLED = env.bool("PLATFORM_TIKTOK_ENABLED", default=True)
PLATFORM_INSTAGRAM_ENABLED = env.bool("PLATFORM_INSTAGRAM_ENABLED", default=False)
PLATFORM_YOUTUBE_ENABLED = env.bool("PLATFORM_YOUTUBE_ENABLED", default=True)
YOUTUBE_DERIVED_METRICS_APPROVED = env.bool("YOUTUBE_DERIVED_METRICS_APPROVED", default=False)

# Social providers: "official" adapters need app credentials; "fake" is for dev/tests only.
SOCIAL_PROVIDER_MODE = env("SOCIAL_PROVIDER_MODE", default="fake")
TIKTOK_CLIENT_KEY = env("TIKTOK_CLIENT_KEY", default="")
TIKTOK_CLIENT_SECRET = env("TIKTOK_CLIENT_SECRET", default="")
YOUTUBE_API_KEY = env("YOUTUBE_API_KEY", default="")

# Token encryption key for OAuth tokens (Fernet, urlsafe base64 32 bytes)
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")

# Payments (D-008): only mock until a provider is chosen (Q-03)
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", default="mock")
MOCK_PAYMENT_WEBHOOK_SECRET = env("MOCK_PAYMENT_WEBHOOK_SECRET", default="mock-webhook-secret")

# --- Logging ---------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "common.logging.RequestIdFilter"}},
    "formatters": {"json": {"()": "common.logging.JsonFormatter"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json", "filters": ["request_id"]},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
    },
}

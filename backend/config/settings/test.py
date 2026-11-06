from .base import *  # noqa: F401,F403

DEBUG = False
ENV = "test"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only in tests
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SOCIAL_PROVIDER_MODE = "fake"
PAYMENT_PROVIDER = "mock"
FIELD_ENCRYPTION_KEY = "NDK-a6EEtVUQ79LstiJBL-0ub4XuhNWx-2Mcxu2FAq8="  # test-only key
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"auth": "1000/min", "stats_refresh": "1000/min"}}  # noqa: F405

"""Beta on Vercel (D-026): production settings + serverless specifics.

- Neon (Vercel Marketplace) provides DATABASE_URL; Upstash provides REDIS_URL/KV_URL.
- No Celery worker on Vercel: tasks run inside the request (CELERY_TASK_ALWAYS_EAGER).
- Timers (auto-cancel, auto-confirm, payout release) run from GitHub Actions every 15 min and a daily Vercel Cron.
- The site proxies /api/v1 to this project, so client IPs arrive via Vercel's forwarding headers.
"""
import os

os.environ.setdefault("BETA_MODE", "true")
os.environ.setdefault("PAYMENT_PROVIDER", "mock")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("SOCIAL_PROVIDER_MODE", "official")
if not os.environ.get("REDIS_URL") and os.environ.get("KV_URL"):
    os.environ["REDIS_URL"] = os.environ["KV_URL"]  # Upstash integration name
if os.environ.get("VERCEL_URL") and not os.environ.get("DJANGO_ALLOWED_HOSTS"):
    os.environ["DJANGO_ALLOWED_HOSTS"] = ",".join(
        h for h in (os.environ.get("VERCEL_URL"), os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")) if h)
# Shared Vercel proxy addresses would make per-IP limits global: keep them generous in the beta.
os.environ.setdefault("THROTTLE_ANON", "3000/min")
os.environ.setdefault("THROTTLE_AUTH", "120/min")
os.environ.setdefault("NUM_PROXIES", "0")
os.environ.setdefault("DB_CONN_MAX_AGE", "0")  # serverless: no persistent connections; Neon pooler handles it

from .prod import *  # noqa: E402,F403

SECURE_SSL_REDIRECT = False  # Vercel terminates TLS and redirects itself
SESSION_COOKIE_DOMAIN = None  # cookies belong to the site origin that proxies us
CSRF_COOKIE_DOMAIN = None
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}  # noqa: F405

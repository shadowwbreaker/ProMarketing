"""Run all periodic timers once (D-026): replaces celery beat where no worker exists (Vercel beta).

Called by GitHub Actions every 15 minutes and by a daily Vercel Cron, authorised with CRON_SECRET.
Only internal timers and retention cleanup run here — never a platform poll (D-004).
"""
import hmac
import logging
import os

from django.conf import settings
from django.utils.module_loading import import_string
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

log = logging.getLogger(__name__)


def run_all_timers() -> dict:
    done = {}
    for name, spec in settings.CELERY_BEAT_SCHEDULE.items():
        try:
            import_string(spec["task"])()  # call the task function directly, synchronously
            done[name] = "ok"
        except Exception as e:  # one failing timer must not stop the others
            log.exception("timer %s failed", name)
            done[name] = f"error: {type(e).__name__}"
    return done


class TickView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        secret = os.environ.get("CRON_SECRET", "")
        given = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not secret or not hmac.compare_digest(given, secret):
            return Response({"error": {"code": "forbidden", "message": "Forbidden"}}, status=403)
        ran = run_all_timers()
        return Response({"ran": ran}, status=200 if all(result == "ok" for result in ran.values()) else 503)

    post = get

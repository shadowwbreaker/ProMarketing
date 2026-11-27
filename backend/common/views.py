from threading import Lock

from django.core.cache import cache
from django.core.cache.backends.locmem import LocMemCache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

_READINESS_TTL_SECONDS = 5
_readiness_cache = LocMemCache("health-readiness", {})
_readiness_lock = Lock()


class LiveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []  # monitoring and load balancers must always get an answer

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response({"status": "ok"})


class MetaView(APIView):
    """Public flags the SPA needs before login (beta banner, instant test payment)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        from django.conf import settings

        return Response({
            "beta": settings.BETA_MODE,
            "payment_provider": settings.PAYMENT_PROVIDER,
            "document_attachments": bool(settings.ATTACHMENT_CLAMAV_HOST),
        })


class ReadyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []  # monitoring and load balancers must always get an answer

    @extend_schema(responses={200: dict, 503: dict})
    def get(self, request):
        checks = _readiness_cache.get("checks")
        if checks is None:
            with _readiness_lock:
                checks = _readiness_cache.get("checks")
                if checks is None:
                    checks = self.probe_dependencies()
                    _readiness_cache.set("checks", checks, timeout=_READINESS_TTL_SECONDS)
        ok = all(value == "ok" for value in checks.values())
        return Response({"status": "ok" if ok else "degraded", "checks": checks}, status=200 if ok else 503)

    @staticmethod
    def probe_dependencies():
        checks = {}
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            checks["database"] = "ok"
        except Exception:  # noqa: BLE001
            checks["database"] = "error"
        try:
            cache.set("health:ping", "1", 5)
            checks["cache"] = "ok" if cache.get("health:ping") == "1" else "error"
        except Exception:  # noqa: BLE001
            checks["cache"] = "error"
        return checks

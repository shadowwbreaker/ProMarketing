import uuid

from .logging import request_id_var


class RequestIdMiddleware:
    """Attach a request id (incoming X-Request-ID or generated) to logs and responses."""

    header = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(self.header, "")
        rid = incoming if incoming and len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        request.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response["X-Request-ID"] = rid
        return response


class SecurityHeadersMiddleware:
    """API responses are data only: forbid rendering/embedding them (defence in depth against XSS/clickjacking)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response

from datetime import timedelta

from django.utils import timezone


class LastSeenMiddleware:
    """Track last activity (used in dispute scenario 1: seller not responding). Throttled to 1 write/5 min."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = timezone.now()
            if user.last_seen_at is None or now - user.last_seen_at > timedelta(minutes=5):
                type(user).objects.filter(pk=user.pk).update(last_seen_at=now)
        return response

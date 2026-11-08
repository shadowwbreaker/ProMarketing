from rest_framework.throttling import UserRateThrottle


class SignedInUserThrottle(UserRateThrottle):
    """Per-user limit for signed-in users only.

    DRF's UserRateThrottle also counts anonymous requests by IP, which would silently cap visitors at the
    (higher) user rate; anonymous traffic is governed by AnonRateThrottle instead.
    """

    def get_cache_key(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return None
        return super().get_cache_key(request, view)

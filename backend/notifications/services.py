"""Notification fan-out (roadmap 8.2). In-app notifications now; email channel added in Phase 8."""
from .models import Notification


def notify(user, type_: str, title: str, body: str = "", **payload) -> Notification:
    return Notification.objects.create(user=user, type=type_, title=title, body=body,
                                       payload={k: str(v) for k, v in payload.items()})

"""Notification fan-out (roadmap 8.2): in-app always, email for important events."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .models import Notification

logger = logging.getLogger(__name__)

EMAIL_TYPES = {
    "order.new", "order.paid", "order.accepted", "order.published", "order.confirmed", "order.deadline_soon",
    "order.deadline_missed", "order.expired", "dispute.opened", "dispute.evidence_requested", "dispute.decided",
    "refund.started", "refund.done", "payout.available", "payout.started", "payout.paid",
}


def notify(user, type_: str, title: str, body: str = "", **payload) -> Notification:
    n = Notification.objects.create(user=user, type=type_, title=title, body=body,
                                    payload={k: str(v) for k, v in payload.items()})
    if type_ in EMAIL_TYPES and user.is_email_verified:
        link = f"{settings.FRONTEND_URL}/orders/{payload['order']}" if "order" in payload else settings.FRONTEND_URL

        def _send():
            try:
                send_mail(f"ProMarketing: {title}", f"{body}\n\n{link}", None, [user.email])
            except Exception:  # noqa: BLE001 — email failure must never break the business operation
                logger.exception("notification email failed type=%s", type_)

        transaction.on_commit(_send)
    return n

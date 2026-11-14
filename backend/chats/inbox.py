from datetime import timedelta

from django.db.models import CharField, OuterRef, Q, Subquery
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.avatar import avatar_url
from common.permissions import IsActiveUser
from notifications.models import Notification
from orders.models import Order

from .models import ChatMessage, DirectMessage

INBOX_TYPES = ("order.new", "chat.message")


def order_notifications(user):
    return Notification.objects.filter(user=user, read_at__isnull=True, type__in=INBOX_TYPES)


def peer_summary(user):
    return {
        "id": str(user.pk), "display_name": user.profile.display_name,
        "avatar_url": avatar_url(user.profile), "date_joined": user.date_joined,
        "online": bool(user.last_seen_at and timezone.now() - user.last_seen_at < timedelta(minutes=10)),
        "blocked": user.status == user.Status.BLOCKED,
    }


class OrderThreads(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        user = request.user
        latest = ChatMessage.objects.filter(chat__order_id=OuterRef("pk"), deleted_at__isnull=True).order_by("-created_at", "-pk")
        orders = list(
            Order.objects.filter(Q(buyer=user) | Q(seller=user), paid_at__isnull=False, chat__isnull=False)
            .select_related("buyer__profile", "seller__profile", "current_terms_version")
            .annotate(last_message=Subquery(latest.values("body")[:1]),
                      last_message_at=Coalesce(Subquery(latest.values("created_at")[:1]), "paid_at"))
            .order_by("-last_message_at", "-pk")[:100]
        )
        unread = set(order_notifications(user).filter(payload__order__in=[str(o.pk) for o in orders])
                     .values_list("payload__order", flat=True))
        return Response({"results": [
            {
                "order_id": str(order.pk), "role": "seller" if order.seller_id == user.pk else "buyer",
                "user": peer_summary(order.buyer if order.seller_id == user.pk else order.seller),
                "brand": order.current_terms_version.brand if order.current_terms_version else "",
                "status": order.status, "last_message": (order.last_message or "Оплата получена")[:120],
                "last_message_at": order.last_message_at, "unread": int(str(order.pk) in unread),
            }
            for order in orders
        ]})


class InboxStatus(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        user = request.user
        direct = DirectMessage.objects.filter(Q(thread__user_a=user) | Q(thread__user_b=user), read_at__isnull=True)
        order_ids = Order.objects.filter(Q(buyer=user) | Q(seller=user), paid_at__isnull=False)
        # Checkout notifications are created on payment, but a pre-payment chat can also have messages.
        paid_ids = order_ids.annotate(order_key=Cast("pk", CharField())).values("order_key")
        order_unread = (order_notifications(user).annotate(order_key=KeyTextTransform("order", "payload"))
                        .filter(order_key__in=Subquery(paid_ids)).exists())
        return Response({"unread": order_unread or direct.exclude(author=user).exists(),
                         "has_received_orders": order_ids.filter(seller=user).exists()})

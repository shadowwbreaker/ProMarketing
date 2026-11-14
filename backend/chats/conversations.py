from uuid import UUID

from django.db.models import Case, CharField, F, Max, OuterRef, Q, Subquery, When
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from common.exceptions import DomainError
from common.permissions import IsActiveUser
from notifications.models import Notification

from .direct import get_thread
from .inbox import order_notifications, paid_orders, peer_summary, visible_order_messages, with_last_order_message
from .models import DirectMessage, DirectThread
from .views import MessageSerializer

PAGE_SIZE = 60


@method_decorator(never_cache, name="dispatch")
class Conversations(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        me = request.user
        directs = DirectThread.objects.filter(
            Q(user_a=me) | Q(user_b=me), last_message_at__isnull=False,
        ).select_related("user_a__profile", "user_b__profile")
        latest_direct = DirectMessage.objects.filter(thread=OuterRef("pk")).order_by("-created_at", "-pk")
        unread_direct = latest_direct.filter(read_at__isnull=True).exclude(author=me)
        rows = {}
        for thread in directs.annotate(
            last_body=Subquery(latest_direct.values("body")[:1]),
            unread_message=Subquery(unread_direct.values("pk")[:1]),
        ):
            peer = thread.user_b if thread.user_a_id == me.pk else thread.user_a
            rows[peer.pk] = {"user": peer_summary(peer), "last_message": (thread.last_body or "")[:120],
                             "last_message_at": thread.last_message_at, "unread": bool(thread.unread_message)}

        orders = paid_orders(me).annotate(peer_id=Case(When(seller=me, then=F("buyer_id")), default=F("seller_id")))
        order_keys = orders.annotate(order_key=Cast("pk", CharField()))
        # The notification payload stores UUIDs as JSON strings. Compare those strings with the paid order IDs.
        unread = order_notifications(me).annotate(order_key=KeyTextTransform("order", "payload")).values("order_key")
        unread_peers = set(order_keys.filter(order_key__in=Subquery(unread)).values_list("peer_id", flat=True))
        for order in with_last_order_message(orders).select_related("buyer__profile", "seller__profile").order_by(
            "peer_id", "-last_message_at", "-pk",
        ).distinct("peer_id"):
            peer = order.buyer if order.seller_id == me.pk else order.seller
            row = rows.get(peer.pk)
            order_unread = peer.pk in unread_peers
            if row is None or order.last_message_at >= row["last_message_at"]:
                rows[peer.pk] = {"user": peer_summary(peer), "last_message": (order.last_message or "Заказ")[:120],
                                 "last_message_at": order.last_message_at, "unread": order_unread or bool(row and row["unread"])}
            else:
                row["unread"] = row["unread"] or order_unread

        return Response({"results": sorted(rows.values(), key=lambda row: row["last_message_at"], reverse=True)})


def before_cursor(messages, cursor):
    try:
        timestamp, message_id = cursor.rsplit("|", 1)
        timestamp, message_id = parse_datetime(timestamp), UUID(message_id)
        if timestamp is None or timezone.is_naive(timestamp):
            raise ValueError
    except ValueError as exc:
        raise DomainError("Неверный курсор переписки", code="invalid_cursor", status_code=400) from exc
    return messages.filter(Q(created_at__lt=timestamp) | Q(created_at=timestamp, pk__lt=message_id))


@method_decorator(never_cache, name="dispatch")
class Conversation(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, user_id):
        me = request.user
        peer = get_object_or_404(User.objects.select_related("profile"), pk=user_id, is_active=True)
        if peer.pk == me.pk:
            raise DomainError("Нельзя написать самому себе", code="self_message", status_code=400)
        opened_at = timezone.now()
        orders = paid_orders(me).filter(Q(buyer=peer) | Q(seller=peer))
        thread = get_thread(me, peer, create=False)
        direct = DirectMessage.objects.filter(thread=thread) if thread else DirectMessage.objects.none()
        order_chat = visible_order_messages().filter(chat__order__in=orders)
        before = request.query_params.get("before")
        version = ""
        if before:
            direct = before_cursor(direct, before)
            order_chat = before_cursor(order_chat, before)
        else:
            versions = (direct.aggregate(latest=Max("updated_at"))["latest"],
                        order_chat.aggregate(latest=Max("updated_at"))["latest"],
                        orders.aggregate(latest=Max("updated_at"))["latest"])
            version = "|".join(value.isoformat() if value else "" for value in versions)
            if request.query_params.get("version") == version:
                return Response({"unchanged": True})

        recent = "-created_at", "-pk"
        personal = direct.order_by(*recent)[:PAGE_SIZE + 1]
        linked = order_chat.select_related("author__profile", "chat__order", "order_brief").prefetch_related(
            "attachments",
        ).order_by(*recent)[:PAGE_SIZE + 1]
        messages = sorted([*personal, *linked], key=lambda m: (m.created_at, m.pk), reverse=True)
        next_cursor = None
        if len(messages) > PAGE_SIZE:
            earliest = messages[PAGE_SIZE - 1]
            next_cursor = f"{earliest.created_at.isoformat()}|{earliest.pk}"
        result = []
        for message in reversed(messages[:PAGE_SIZE]):
            if isinstance(message, DirectMessage):
                author = me if message.author_id == me.pk else peer
                result.append({"id": str(message.pk), "kind": "user", "body": message.body,
                               "author": {"id": str(author.pk), "display_name": author.profile.display_name},
                               "created_at": message.created_at, "attachments": [], "edited": False, "deleted_at": None})
            else:
                data = MessageSerializer(message).data
                data.pop("contact_signal", None)
                result.append({**data, "order_id": str(message.chat.order_id)})

        marked = 0
        summaries = []
        if not before:
            summaries = [{"id": str(order.pk), "title": order.current_terms_version.brand if order.current_terms_version else "",
                          "status": order.status, "locked": bool(getattr(getattr(order, "chat", None), "locked_at", None))}
                         for order in orders.select_related("current_terms_version", "chat").order_by("-paid_at", "-pk")]
            if request.query_params.get("read") == "1":
                marked = direct.filter(read_at__isnull=True, created_at__lte=opened_at).exclude(author=me).update(read_at=opened_at)
                marked += order_notifications(me).filter(
                    payload__order__in=[order["id"] for order in summaries], created_at__lte=opened_at,
                ).update(read_at=opened_at)
                Notification.objects.filter(user=me, type="direct.message", payload__sender=str(peer.pk),
                                            created_at__lte=opened_at, read_at__isnull=True).update(read_at=opened_at)

        return Response({"results": result, "next": next_cursor, "orders": summaries,
                         "version": version, "marked_read": marked})

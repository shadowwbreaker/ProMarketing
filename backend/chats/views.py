from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from common.permissions import IsActiveUser

from . import services
from .inbox import order_notifications
from .models import ChatMessage


class MessageSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    edited = serializers.SerializerMethodField()
    order_brief = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ["id", "kind", "author", "body", "attachments", "created_at", "edited", "deleted_at", "contact_signal", "order_brief"]

    def get_order_brief(self, m) -> dict | None:
        if m.order_brief_id is None:
            return None
        from orders.views import TermsSerializer

        return {**TermsSerializer(m.order_brief).data, "results_report": m.chat.order.results_report}

    def get_author(self, m):
        if not m.author_id:
            return None
        o = m.chat.order
        return {"id": str(m.author_id), "role": "buyer" if m.author_id == o.buyer_id else "seller",
                "display_name": m.author.profile.display_name}

    def get_body(self, m):
        return "" if m.deleted_at and not self.context.get("staff") else m.body

    def get_edited(self, m):
        return m.revision > 1

    def get_attachments(self, m):
        if m.deleted_at and not self.context.get("staff"):
            return []
        return [{"id": str(a.pk), "name": a.original_name, "mime": a.mime, "size": a.size, "sha256": a.sha256}
                for a in m.attachments.all()]


class Messages(APIView):
    permission_classes = [IsActiveUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"

    def get(self, request, pk):
        chat = services.get_chat(pk, request.user)
        opened_at = timezone.now()
        qs = chat.messages.select_related("author__profile", "chat__order", "order_brief").prefetch_related("attachments")
        if after := request.query_params.get("after"):
            messages = list(qs.filter(created_at__gt=after).order_by("created_at", "pk")[:500])
        else:
            messages = list(qs.order_by("-created_at", "-pk")[:500])[::-1]
        staff = request.user.has_perm_code("staff.view_orders")
        data = MessageSerializer(messages, many=True, context={"staff": staff}).data
        if not staff:
            for d in data:
                d.pop("contact_signal", None)
        marked = 0
        if not after and request.query_params.get("read") == "1" and request.user.pk in (chat.order.buyer_id, chat.order.seller_id):
            marked = order_notifications(request.user).filter(payload__order=str(pk), created_at__lte=opened_at).update(read_at=opened_at)
        return Response({"locked": bool(chat.locked_at), "results": data, "marked_read": marked})

    def post(self, request, pk):
        msg = services.post_message(pk, user=request.user, body=request.data.get("body", ""),
                                    attachments=request.data.get("attachments") or [])
        out = MessageSerializer(ChatMessage.objects.select_related("author__profile", "chat__order").get(pk=msg.pk)).data
        out["warning"] = "Договариваться и платить вне платформы запрещено — так вы теряете защиту сделки." if msg.contact_signal else ""
        out.pop("contact_signal", None)
        return Response(out, status=201)


class MessageDetail(APIView):
    permission_classes = [IsActiveUser]

    def patch(self, request, pk, msg_id):
        get_object_or_404(ChatMessage, pk=msg_id, chat__order_id=pk)
        msg = services.edit_message(msg_id, user=request.user, body=request.data.get("body", ""))
        return Response(MessageSerializer(msg).data)

    def delete(self, request, pk, msg_id):
        get_object_or_404(ChatMessage, pk=msg_id, chat__order_id=pk)
        services.delete_message(msg_id, user=request.user)
        return Response(status=204)

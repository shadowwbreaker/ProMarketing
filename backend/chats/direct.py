"""Pre-order direct messages (FunPay-style "write to the seller before paying").

Same anti-circumvention rule as order chats: contacts/requisites raise a moderator signal and a warning.
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import User
from common.exceptions import DomainError
from common.permissions import IsActiveUser

from .models import DirectMessage, DirectThread
from .services import has_contact_signal

WARNING = "Договариваться и платить вне платформы запрещено — так вы теряете защиту сделки."


def _pair(u1, u2):
    return (u1, u2) if str(u1.pk) < str(u2.pk) else (u2, u1)


def get_thread(me, other, *, create: bool) -> DirectThread | None:
    a, b = _pair(me, other)
    t = DirectThread.objects.filter(user_a=a, user_b=b).first()
    if t or not create:
        return t
    try:
        with transaction.atomic():
            return DirectThread.objects.create(user_a=a, user_b=b)
    except IntegrityError:
        return DirectThread.objects.get(user_a=a, user_b=b)


def _msg(m: DirectMessage, me) -> dict:
    return {"id": str(m.pk), "mine": m.author_id == me.pk, "body": m.body, "created_at": m.created_at}


class DirectMessages(APIView):
    permission_classes = [IsActiveUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"

    def _other(self, request, user_id):
        other = get_object_or_404(User.objects.select_related("profile"), pk=user_id, is_active=True)
        if other.pk == request.user.pk:
            raise DomainError("Нельзя написать самому себе", code="self_message", status_code=400)
        return other

    def get(self, request, user_id):
        other = self._other(request, user_id)
        t = get_thread(request.user, other, create=False)
        if not t:
            return Response({"results": []})
        t.messages.filter(read_at__isnull=True).exclude(author=request.user).update(read_at=timezone.now())
        return Response({"results": [_msg(m, request.user) for m in t.messages.order_by("created_at")[:300]]})

    def post(self, request, user_id):
        other = self._other(request, user_id)
        if other.status == User.Status.BLOCKED:
            raise DomainError("Пользователь заблокирован", code="user_blocked", status_code=400)
        body = (request.data.get("body") or "").strip()
        if not body or len(body) > 2000:
            raise DomainError("Сообщение пустое или длиннее 2000 символов", code="bad_body", status_code=400)
        t = get_thread(request.user, other, create=True)
        signal = has_contact_signal(body)
        m = DirectMessage.objects.create(thread=t, author=request.user, body=body, contact_signal=signal)
        DirectThread.objects.filter(pk=t.pk).update(last_message_at=m.created_at)
        from notifications.services import notify

        notify(other, "direct.message", f"Новое сообщение от {request.user.profile.display_name}", body[:200],
               sender=request.user.pk)
        out = _msg(m, request.user)
        out["warning"] = WARNING if signal else ""
        return Response(out, status=201)


class DirectThreads(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        from django.db.models import Q

        me = request.user
        qs = (DirectThread.objects.filter(Q(user_a=me) | Q(user_b=me), last_message_at__isnull=False)
              .select_related("user_a__profile", "user_b__profile").order_by("-last_message_at")[:100])
        out = []
        for t in qs:
            other = t.user_b if t.user_a_id == me.pk else t.user_a
            last = t.messages.order_by("-created_at").first()
            from accounts.avatar import avatar_url

            online = bool(other.last_seen_at and timezone.now() - other.last_seen_at < timedelta(minutes=10))
            out.append({"user": {"id": str(other.pk), "display_name": other.profile.display_name,
                                 "avatar_url": avatar_url(other.profile), "online": online,
                                 "date_joined": other.date_joined, "blocked": other.status == User.Status.BLOCKED},
                        "last_message": last.body[:120] if last else "", "last_message_at": t.last_message_at,
                        "unread": t.messages.filter(read_at__isnull=True).exclude(author=me).count()})
        return Response({"results": out})


class DirectUnread(APIView):
    """Badge for "Сообщения" in the header."""

    permission_classes = [IsActiveUser]

    def get(self, request):
        from django.db.models import Q

        me = request.user
        n = (DirectMessage.objects.filter(Q(thread__user_a=me) | Q(thread__user_b=me), read_at__isnull=True)
             .exclude(author=me).count())
        return Response({"unread": n})

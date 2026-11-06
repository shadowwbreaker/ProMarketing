"""Order chat (roadmap 8.1). Messages become immutable once a dispute is opened (chat.locked_at)."""
import re
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from common.exceptions import DomainError
from notifications.services import notify

from .models import Chat, ChatMessage, ChatMessageRevision

EDIT_WINDOW = timedelta(minutes=15)

# Scenario 10: signals only (message is delivered, moderator gets a flag). Not an accusation.
_CONTACT_PATTERNS = [
    re.compile(r"(?:\+7|8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}"),        # RU phone
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}"),                                           # email
    re.compile(r"(?i)\b(?:t\.me|wa\.me|telegram\.me|vk\.com|whatsapp)\b"),              # messengers
    re.compile(r"(?i)(?:телеграм|телега|ватсап|вотсап|напиши мне в|переведи на карту|оплата напрямую)"),
    re.compile(r"\b(?:\d[ -]?){16}\b"),                                                    # card-like number
]


def has_contact_signal(text: str) -> bool:
    return any(p.search(text or "") for p in _CONTACT_PATTERNS)


def _participant(chat: Chat, user) -> str:
    o = chat.order
    if user.pk == o.buyer_id:
        return "buyer"
    if user.pk == o.seller_id:
        return "seller"
    if user.has_perm_code("staff.view_orders"):
        return "staff"
    raise DomainError("Нет доступа", code="forbidden", status_code=404)


def get_chat(order_id, user) -> Chat:
    chat = Chat.objects.select_related("order").filter(order_id=order_id).first()
    if not chat:
        raise DomainError("Чат не найден", code="not_found", status_code=404)
    _participant(chat, user)
    return chat


def post_message(order_id, *, user, body: str, attachments=()) -> ChatMessage:
    body = (body or "").strip()
    if not body and not attachments:
        raise DomainError("Пустое сообщение", code="empty_message", status_code=400)
    with transaction.atomic():
        chat = Chat.objects.select_for_update().select_related("order").get(order_id=order_id)
        role = _participant(chat, user)
        if role == "staff":
            raise DomainError("Сотрудники пишут в карточке спора", code="staff_use_dispute", status_code=403)
        from files.models import Attachment

        atts = list(Attachment.objects.filter(pk__in=list(attachments), owner=user, scan_status="clean"))
        if len(atts) != len(set(attachments)):
            raise DomainError("Вложение не найдено", code="bad_attachment", status_code=400)
        msg = ChatMessage.objects.create(chat=chat, author=user, body=body, contact_signal=has_contact_signal(body))
        msg.attachments.set(atts)
        other = chat.order.seller if role == "buyer" else chat.order.buyer
    notify(other, "chat.message", "Новое сообщение по заказу", body[:120], order=chat.order_id)
    return msg


def system_message(order, text: str) -> ChatMessage | None:
    chat = Chat.objects.filter(order=order).first()
    if not chat:
        return None
    return ChatMessage.objects.create(chat=chat, author=None, kind=ChatMessage.Kind.SYSTEM, body=text)


def _editable(msg: ChatMessage, user):
    if msg.author_id != user.pk or msg.kind != ChatMessage.Kind.USER:
        raise DomainError("Можно менять только свои сообщения", code="forbidden", status_code=403)
    if msg.chat.locked_at:
        raise DomainError("По заказу открыт спор — переписка зафиксирована", code="chat_locked", status_code=409)
    if msg.deleted_at:
        raise DomainError("Сообщение удалено", code="deleted")
    if timezone.now() - msg.created_at > EDIT_WINDOW:
        raise DomainError("Изменять сообщение можно в течение 15 минут", code="edit_window_passed", status_code=409)


def edit_message(msg_id, *, user, body: str) -> ChatMessage:
    with transaction.atomic():
        msg = ChatMessage.objects.select_for_update().select_related("chat").get(pk=msg_id)
        _editable(msg, user)
        ChatMessageRevision.objects.create(message=msg, revision=msg.revision, body=msg.body)  # history kept
        msg.body = body.strip()
        msg.revision += 1
        msg.contact_signal = msg.contact_signal or has_contact_signal(msg.body)
        msg.save(update_fields=["body", "revision", "contact_signal", "updated_at"])
    return msg


def delete_message(msg_id, *, user) -> ChatMessage:
    with transaction.atomic():
        msg = ChatMessage.objects.select_for_update().select_related("chat").get(pk=msg_id)
        _editable(msg, user)
        ChatMessageRevision.objects.create(message=msg, revision=msg.revision, body=msg.body)
        msg.deleted_at = timezone.now()
        msg.save(update_fields=["deleted_at", "updated_at"])
    return msg


def lock_chat(order) -> None:
    """Called when a dispute opens: freezes edits/deletes (roadmap 8.1)."""
    Chat.objects.filter(order=order, locked_at__isnull=True).update(locked_at=timezone.now())

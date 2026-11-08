from django.conf import settings
from django.db import models

from common.models import BaseModel


class Chat(BaseModel):
    """One chat per order (roadmap 8.1). Locked for edits once a dispute is opened."""

    order = models.OneToOneField("orders.Order", on_delete=models.PROTECT, related_name="chat")
    locked_at = models.DateTimeField(null=True, blank=True)


class ChatMessage(BaseModel):
    class Kind(models.TextChoices):
        USER = "user", "Сообщение пользователя"
        SYSTEM = "system", "Системное сообщение"

    chat = models.ForeignKey(Chat, on_delete=models.PROTECT, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.USER)
    body = models.TextField(max_length=5000)
    attachments = models.ManyToManyField("files.Attachment", blank=True, related_name="+")
    revision = models.PositiveIntegerField(default=1)
    deleted_at = models.DateTimeField(null=True, blank=True)
    contact_signal = models.BooleanField(default=False, help_text="Обнаружены контакты/реквизиты (сценарий 10, сигнал модератору)")

    class Meta:
        indexes = [models.Index(fields=["chat", "created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind="system", author__isnull=True) | models.Q(kind="user", author__isnull=False),
                name="chat_message_author_matches_kind",
            )
        ]


class ChatMessageRevision(BaseModel):
    message = models.ForeignKey(ChatMessage, on_delete=models.PROTECT, related_name="revisions")
    revision = models.PositiveIntegerField()
    body = models.TextField(max_length=5000)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["message", "revision"], name="message_revision_unique")]


class DirectThread(BaseModel):
    """Pre-order conversation between two users ("напишите продавцу перед оплатой").

    Pair is stored ordered (user_a < user_b) so there is exactly one thread per pair.
    """

    user_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    user_b = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user_a", "user_b"], name="direct_thread_pair_unique"),
            models.CheckConstraint(condition=models.Q(user_a__lt=models.F("user_b")), name="direct_thread_ordered_pair"),
        ]


class DirectMessage(BaseModel):
    thread = models.ForeignKey(DirectThread, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    body = models.TextField(max_length=2000)
    read_at = models.DateTimeField(null=True, blank=True)
    contact_signal = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["thread", "created_at"])]

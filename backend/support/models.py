from django.conf import settings
from django.db import models

from common.models import BaseModel, MoneyField


class SupportTicket(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Открыто"
        IN_PROGRESS = "in_progress", "В работе"
        WAITING_USER = "waiting_user", "Ожидает пользователя"
        CLOSED = "closed", "Закрыто"

    class Priority(models.TextChoices):
        LOW = "low", "Низкий"
        NORMAL = "normal", "Обычный"
        HIGH = "high", "Высокий"
        URGENT = "urgent", "Срочный"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tickets")
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.PROTECT, related_name="tickets")
    category = models.CharField(max_length=64)
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_tickets")


class DisputeReason(models.Model):
    """Reference list of complaint reasons (roadmap 9.2)."""

    class AllowedFor(models.TextChoices):
        BUYER = "buyer", "Покупатель"
        SELLER = "seller", "Продавец"
        BOTH = "both", "Обе стороны"

    code = models.CharField(max_length=48, unique=True)
    title = models.CharField(max_length=200)
    allowed_for = models.CharField(max_length=8, choices=AllowedFor.choices)
    sort = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort"]


class DisputeStatus(models.TextChoices):
    OPEN = "OPEN", "Открыт"
    WAITING_SELLER = "WAITING_SELLER", "Ожидает ответа продавца"
    WAITING_BUYER = "WAITING_BUYER", "Ожидает ответа покупателя"
    UNDER_REVIEW = "UNDER_REVIEW", "На рассмотрении"
    EVIDENCE_REQUESTED = "EVIDENCE_REQUESTED", "Запрошены доказательства"
    ESCALATED = "ESCALATED", "Эскалирован"
    RESOLVED = "RESOLVED", "Решён"
    REJECTED = "REJECTED", "Отклонён"
    CLOSED = "CLOSED", "Закрыт"
    APPEALED = "APPEALED", "Апелляция"


ACTIVE_DISPUTE_STATUSES = [
    DisputeStatus.OPEN, DisputeStatus.WAITING_SELLER, DisputeStatus.WAITING_BUYER, DisputeStatus.UNDER_REVIEW,
    DisputeStatus.EVIDENCE_REQUESTED, DisputeStatus.ESCALATED, DisputeStatus.APPEALED,
]


class Dispute(BaseModel):
    class Priority(models.TextChoices):
        NORMAL = "normal", "Обычный"
        HIGH = "high", "Высокий"

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="disputes")
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opened_disputes")
    reason = models.ForeignKey(DisputeReason, on_delete=models.PROTECT, related_name="+")
    description = models.TextField(max_length=10_000)
    status = models.CharField(max_length=24, choices=DisputeStatus.choices, default=DisputeStatus.OPEN, db_index=True)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.NORMAL)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_disputes")
    response_due_at = models.DateTimeField(null=True, blank=True)
    response_overdue = models.BooleanField(default=False, help_text="Сторона не ответила в срок (учитывается, но не решает спор)")
    appeal_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="appeals")
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "-created_at"])]


class DisputeItem(BaseModel):
    """Order items covered by a dispute. One active dispute per item (scenario 15: counter-claims join it)."""

    dispute = models.ForeignKey(Dispute, on_delete=models.PROTECT, related_name="items")
    order_item = models.ForeignKey("orders.OrderItem", on_delete=models.PROTECT, related_name="dispute_items")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order_item"], condition=models.Q(is_active=True), name="one_active_dispute_per_item"),
            models.UniqueConstraint(fields=["dispute", "order_item"], name="dispute_item_unique"),
        ]


class DisputeMessage(BaseModel):
    class Visibility(models.TextChoices):
        ALL = "all", "Все участники"
        STAFF = "staff", "Только сотрудники"

    dispute = models.ForeignKey(Dispute, on_delete=models.PROTECT, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    visibility = models.CharField(max_length=8, choices=Visibility.choices, default=Visibility.ALL)
    body = models.TextField(max_length=10_000)


class DisputeEvidence(BaseModel):
    dispute = models.ForeignKey(Dispute, on_delete=models.PROTECT, related_name="evidence")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    attachment = models.ForeignKey("files.Attachment", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    url = models.URLField(max_length=1000, blank=True)
    description = models.TextField(max_length=4000)
    sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(attachment__isnull=False) | ~models.Q(url=""),
                name="evidence_has_file_or_url",
            )
        ]


class DisputeDecision(BaseModel):
    class Type(models.TextChoices):
        FULL_REFUND = "full_refund", "Полный возврат"
        PARTIAL_REFUND = "partial_refund", "Частичный возврат"
        REJECT = "reject", "Отказ в жалобе"
        REDO = "redo", "Повторное выполнение"
        EXTEND = "extend", "Продление срока"
        IN_FAVOR_OF_SELLER = "in_favor_of_seller", "Подтверждение в пользу продавца"
        REQUEST_EVIDENCE = "request_evidence", "Запрос доказательств"
        ESCALATE = "escalate", "Передача старшему администратору"
        SANCTION = "sanction", "Санкции"

    dispute = models.ForeignKey(Dispute, on_delete=models.PROTECT, related_name="decisions")
    order_item = models.ForeignKey("orders.OrderItem", null=True, blank=True, on_delete=models.PROTECT, related_name="dispute_decisions")
    decision_type = models.CharField(max_length=24, choices=Type.choices)
    refund_amount_minor = MoneyField(null=True, blank=True)
    new_deadline = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(help_text="Обязательный комментарий администратора (roadmap 9.6)")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~models.Q(comment=""), name="decision_comment_required"),
            models.CheckConstraint(
                condition=~models.Q(decision_type="partial_refund") | models.Q(refund_amount_minor__gt=0),
                name="partial_refund_requires_amount",
            ),
        ]


class DisputeAction(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        DONE = "done", "Выполнено"
        FAILED = "failed", "Ошибка"

    decision = models.ForeignKey(DisputeDecision, on_delete=models.PROTECT, related_name="actions")
    action_type = models.CharField(max_length=32)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    refund_request = models.ForeignKey("payments.RefundRequest", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    payout = models.ForeignKey("payments.Payout", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    error = models.TextField(blank=True)


class AdminNote(BaseModel):
    """Internal staff notes, never visible to users."""

    subject_type = models.CharField(max_length=32)
    subject_id = models.UUIDField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    body = models.TextField(max_length=10_000)

    class Meta:
        indexes = [models.Index(fields=["subject_type", "subject_id"])]

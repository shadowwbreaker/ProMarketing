from django.conf import settings
from django.db import models

from common.models import AppendOnlyModel, BaseModel, MoneyField


class Payment(BaseModel):
    class Status(models.TextChoices):
        CREATED = "created", "Создан"
        PENDING = "pending", "Ожидает оплаты"
        SUCCEEDED = "succeeded", "Оплачен"
        CANCELLED = "cancelled", "Отменён"
        FAILED = "failed", "Ошибка"

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=32)
    provider_payment_id = models.CharField(max_length=128, null=True, blank=True)
    amount_minor = MoneyField()
    currency = models.CharField(max_length=3, default="RUB")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CREATED)
    idempotency_key = models.CharField(max_length=64, unique=True)
    confirmation_url = models.URLField(max_length=1000, blank=True)
    succeeded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["provider", "provider_payment_id"], name="payment_provider_id_unique"),
            models.CheckConstraint(condition=models.Q(amount_minor__gt=0), name="payment_amount_positive"),
            models.UniqueConstraint(fields=["order"], condition=models.Q(status="succeeded"), name="one_succeeded_payment_per_order"),
        ]


class PaymentAllocation(BaseModel):
    """How a payment is split across order items (basis for per-item refunds)."""

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    order_item = models.ForeignKey("orders.OrderItem", on_delete=models.PROTECT, related_name="allocations")
    amount_minor = MoneyField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["payment", "order_item"], name="allocation_unique"),
            models.CheckConstraint(condition=models.Q(amount_minor__gt=0), name="allocation_amount_positive"),
        ]


class RefundRequest(BaseModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Запрошен"
        PENDING = "pending", "В обработке у провайдера"
        PENDING_RECONCILIATION = "pending_reconciliation", "Требует сверки"
        SUCCEEDED = "succeeded", "Выполнен"
        FAILED = "failed", "Ошибка"

    order_item = models.ForeignKey("orders.OrderItem", on_delete=models.PROTECT, related_name="refunds")
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    dispute_decision = models.ForeignKey("support.DisputeDecision", null=True, blank=True, on_delete=models.PROTECT, related_name="refunds")
    amount_minor = MoneyField()
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.REQUESTED)
    reason = models.TextField()
    provider_refund_id = models.CharField(max_length=128, null=True, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                     help_text="Пусто — инициировано системой (таймер)")

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount_minor__gt=0), name="refund_amount_positive")]


class Payout(BaseModel):
    """Payout to seller per order item (D-014): HOLD 48h after buyer confirmation → AVAILABLE → paid by provider."""

    class Status(models.TextChoices):
        HOLD = "hold", "Период ожидания"
        SUSPENDED = "suspended", "Приостановлена (спор)"
        AVAILABLE = "available", "Доступна к выводу"
        REQUESTED = "requested", "Запрошена у провайдера"
        PENDING_RECONCILIATION = "pending_reconciliation", "Требует сверки"
        PAID = "paid", "Выплачена"
        FAILED = "failed", "Ошибка"
        CANCELLED = "cancelled", "Отменена (возврат)"

    order_item = models.OneToOneField("orders.OrderItem", on_delete=models.PROTECT, related_name="payout")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payouts")
    amount_minor = MoneyField()
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.HOLD)
    available_at = models.DateTimeField()
    provider_payout_id = models.CharField(max_length=128, null=True, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount_minor__gte=0), name="payout_amount_non_negative")]
        indexes = [models.Index(fields=["status", "available_at"])]


class PaymentWebhookEvent(BaseModel):
    provider = models.CharField(max_length=32)
    provider_event_id = models.CharField(max_length=128)
    type = models.CharField(max_length=64)
    raw_body = models.TextField()
    signature_valid = models.BooleanField()
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["provider", "provider_event_id"], name="webhook_event_unique")
        ]


class FinancialLedgerEntry(BaseModel, AppendOnlyModel):
    """Journal mirroring provider operations. Not a balance, not money storage (roadmap 7.4)."""

    class Kind(models.TextChoices):
        PAYMENT_SUCCEEDED = "payment_succeeded", "Платёж получен провайдером"
        REFUND_REQUESTED = "refund_requested", "Возврат запрошен"
        REFUND_SUCCEEDED = "refund_succeeded", "Возврат выполнен"
        REFUND_FAILED = "refund_failed", "Возврат не выполнен"
        PAYOUT_HOLD = "payout_hold", "Выплата в ожидании"
        PAYOUT_SUSPENDED = "payout_suspended", "Выплата приостановлена"
        PAYOUT_AVAILABLE = "payout_available", "Выплата доступна"
        PAYOUT_REQUESTED = "payout_requested", "Выплата запрошена"
        PAYOUT_PAID = "payout_paid", "Выплата выполнена"
        PAYOUT_FAILED = "payout_failed", "Выплата не выполнена"
        PLATFORM_FEE = "platform_fee", "Комиссия платформы"

    order_item = models.ForeignKey("orders.OrderItem", null=True, blank=True, on_delete=models.PROTECT, related_name="ledger")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    amount_minor = MoneyField()
    currency = models.CharField(max_length=3, default="RUB")
    provider = models.CharField(max_length=32)
    provider_ref = models.CharField(max_length=128, blank=True)
    meta = models.JSONField(default=dict, blank=True)

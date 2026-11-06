from django.conf import settings
from django.db import models

from common.models import AppendOnlyModel, BaseModel, MoneyField


class OrderStatus(models.TextChoices):
    """Order / order item lifecycle (roadmap 6.2)."""

    DRAFT = "DRAFT", "Черновик"
    AWAITING_PAYMENT = "AWAITING_PAYMENT", "Ожидает оплаты"
    PAID = "PAID", "Оплачен"
    AWAITING_SELLER_ACCEPTANCE = "AWAITING_SELLER_ACCEPTANCE", "Ожидает принятия продавцом"
    IN_PROGRESS = "IN_PROGRESS", "В работе"
    AWAITING_PUBLICATION = "AWAITING_PUBLICATION", "Ожидает публикации"
    PUBLISHED = "PUBLISHED", "Опубликовано"
    AWAITING_BUYER_CONFIRMATION = "AWAITING_BUYER_CONFIRMATION", "Ожидает подтверждения покупателем"
    COMPLETED = "COMPLETED", "Выполнен"
    DISPUTED = "DISPUTED", "Спор"
    CANCELLED = "CANCELLED", "Отменён"
    REFUND_PENDING = "REFUND_PENDING", "Возврат в обработке"
    REFUNDED = "REFUNDED", "Возвращён"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED", "Частично возвращён"
    EXPIRED = "EXPIRED", "Истёк"


class Order(BaseModel):
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchases")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales")
    network = models.ForeignKey("catalog.AccountNetwork", null=True, blank=True, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=32, choices=OrderStatus.choices, default=OrderStatus.DRAFT, db_index=True,
                              help_text="Агрегированный статус, выводится из статусов позиций")
    total_minor = MoneyField(default=0)
    currency = models.CharField(max_length=3, default="RUB")
    fee_bps = models.PositiveIntegerField(help_text="Комиссия платформы, зафиксированная при создании (D-015)")
    current_terms_version = models.ForeignKey("OrderTermsVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["buyer", "-created_at"]), models.Index(fields=["seller", "-created_at"])]
        constraints = [
            models.CheckConstraint(condition=~models.Q(buyer=models.F("seller")), name="order_buyer_not_seller"),
            models.CheckConstraint(condition=models.Q(fee_bps__lte=10_000), name="order_fee_bps_range"),
        ]


class OrderTermsVersion(BaseModel, AppendOnlyModel):
    """Immutable snapshot of order requirements. New version only with consent of both sides (D-011)."""

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="terms_versions")
    version = models.PositiveIntegerField()
    brand = models.CharField(max_length=200)
    site_url = models.URLField(max_length=500, blank=True)
    brief = models.TextField(max_length=10_000)
    ad_text = models.TextField(blank=True, max_length=5_000)
    cta = models.CharField(max_length=300, blank=True)
    ad_format = models.CharField(max_length=32)
    links = models.JSONField(default=list, blank=True)
    publish_deadline = models.DateTimeField(null=True, blank=True)
    placement_days = models.PositiveSmallIntegerField(default=30)
    extra_requirements = models.TextField(blank=True, max_length=5_000)
    platform_removal_policy = models.CharField(
        max_length=32, default="refund_or_repeat",
        help_text="Что происходит, если платформа удалила видео (сценарий 13)",
    )
    materials_deadline = models.DateTimeField(null=True, blank=True, help_text="Срок передачи материалов покупателем")
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    agreed_by_buyer_at = models.DateTimeField(null=True, blank=True)
    agreed_by_seller_at = models.DateTimeField(null=True, blank=True)
    content_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order", "version"], name="terms_version_unique")]


class OrderItem(BaseModel):
    """Each account in an order is a separate item with own price, status and evidence (roadmap 4.4, 6.5)."""

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    social_account = models.ForeignKey("social_data.SocialAccount", on_delete=models.PROTECT, related_name="order_items")
    offer = models.ForeignKey("catalog.AdvertisingOffer", on_delete=models.PROTECT, related_name="order_items")
    price_minor = MoneyField()
    fee_minor = MoneyField(default=0)
    seller_amount_minor = MoneyField(default=0)
    status = models.CharField(max_length=32, choices=OrderStatus.choices, default=OrderStatus.DRAFT, db_index=True)
    accept_deadline = models.DateTimeField(null=True, blank=True)
    publish_deadline = models.DateTimeField(null=True, blank=True)
    placement_until = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    confirm_deadline = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    payout_available_at = models.DateTimeField(null=True, blank=True, help_text="confirmed_at + 48 ч (D-014)")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(price_minor__gt=0), name="item_price_positive"),
            models.CheckConstraint(
                condition=models.Q(fee_minor__gte=0) & models.Q(seller_amount_minor__gte=0),
                name="item_amounts_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(status="DRAFT") | models.Q(fee_minor__lte=models.F("price_minor")),
                name="item_fee_not_above_price",
            ),
            models.UniqueConstraint(fields=["order", "social_account"], name="item_account_unique_in_order"),
        ]
        indexes = [models.Index(fields=["status", "accept_deadline"]), models.Index(fields=["status", "confirm_deadline"])]


class PublicationProof(BaseModel):
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name="proofs")
    video_url = models.URLField(max_length=500)
    profile_url = models.URLField(max_length=500)
    screenshot = models.ForeignKey("files.Attachment", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    published_at = models.DateTimeField()
    notes = models.TextField(blank=True, max_length=4000)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")


class PublicationCheck(BaseModel):
    """Event-driven one-off check that a published video is still available (D-010). Never periodic."""

    class Trigger(models.TextChoices):
        PROOF = "proof", "Отправка доказательства"
        BUYER = "buyer", "Запрос покупателя"
        ADMIN = "admin", "Проверка администратором"
        WINDOW_END = "window_end", "Окончание окна подтверждения"
        PLACEMENT_END = "placement_end", "Окончание срока размещения"

    class Result(models.TextChoices):
        FOUND = "found", "Найдено"
        NOT_FOUND = "not_found", "Не найдено"
        UNAVAILABLE = "unavailable", "Проверка недоступна"
        ERROR = "error", "Ошибка"

    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name="publication_checks")
    trigger = models.CharField(max_length=16, choices=Trigger.choices)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    result = models.CharField(max_length=16, choices=Result.choices)
    details = models.JSONField(default=dict, blank=True)
    checked_at = models.DateTimeField()


class OrderEvent(BaseModel, AppendOnlyModel):
    """Append-only, hash-chained order history (per order chain)."""

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="events")
    order_item = models.ForeignKey(OrderItem, null=True, blank=True, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    type = models.CharField(max_length=64)
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    seq = models.PositiveIntegerField()
    prev_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order", "seq"], name="order_event_seq_unique")]
        ordering = ["order", "seq"]

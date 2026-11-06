from django.conf import settings
from django.db import models

from common.models import BaseModel, MoneyField


class AdFormat(models.TextChoices):
    """Advertising formats (roadmap 4.2)."""

    INTEGRATION = "integration", "Интеграция внутри ролика"
    DEDICATED = "dedicated", "Отдельный рекламный ролик"
    MENTION = "mention", "Упоминание бренда"
    PRODUCT_DEMO = "product_demo", "Демонстрация продукта"
    INSERT = "insert", "Рекламная вставка"
    LINK_IN_DESCRIPTION = "link_in_description", "Ссылка в описании"
    PINNED_COMMENT = "pinned_comment", "Закреплённый комментарий"
    OTHER = "other", "Другой формат"


class AdvertisingOffer(BaseModel):
    social_account = models.ForeignKey("social_data.SocialAccount", on_delete=models.PROTECT, related_name="offers")
    ad_format = models.CharField(max_length=32, choices=AdFormat.choices)
    title = models.CharField(max_length=120, blank=True)
    price_minor = MoneyField()
    currency = models.CharField(max_length=3, default="RUB")
    conditions = models.TextField(blank=True, max_length=4000)
    placement_days = models.PositiveSmallIntegerField(default=30, help_text="Минимальный срок нахождения публикации")
    publish_within_days = models.PositiveSmallIntegerField(default=7, help_text="Срок публикации после принятия")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(price_minor__gt=0), name="offer_price_positive"),
            models.CheckConstraint(condition=models.Q(publish_within_days__gte=1), name="offer_publish_within_positive"),
            models.UniqueConstraint(
                fields=["social_account", "ad_format"],
                condition=models.Q(is_active=True),
                name="one_active_offer_per_format",
            ),
        ]
        indexes = [models.Index(fields=["is_active", "price_minor"])]


class AccountNetwork(BaseModel):
    """Seller-defined bundle of own accounts (roadmap 4.4)."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="networks")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True, max_length=4000)
    total_price_minor = MoneyField(null=True, blank=True, help_text="Цена всей сетки; пусто = сумма позиций")
    currency = models.CharField(max_length=3, default="RUB")
    conditions = models.TextField(blank=True, max_length=4000)
    allow_partial_purchase = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_price_minor__isnull=True) | models.Q(total_price_minor__gt=0),
                name="network_total_price_positive",
            )
        ]


class NetworkItem(BaseModel):
    network = models.ForeignKey(AccountNetwork, on_delete=models.CASCADE, related_name="items")
    social_account = models.ForeignKey("social_data.SocialAccount", on_delete=models.PROTECT, related_name="network_items")
    offer = models.ForeignKey(AdvertisingOffer, on_delete=models.PROTECT, related_name="network_items")
    price_minor = MoneyField(help_text="Цена аккаунта внутри сетки")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["network", "social_account"], name="network_account_unique"),
            models.CheckConstraint(condition=models.Q(price_minor__gt=0), name="network_item_price_positive"),
        ]

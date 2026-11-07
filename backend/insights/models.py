from django.conf import settings
from django.db import models

from common.models import BaseModel


class Favorite(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    social_account = models.ForeignKey("social_data.SocialAccount", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    network = models.ForeignKey("catalog.AccountNetwork", null=True, blank=True, on_delete=models.CASCADE, related_name="+")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(social_account__isnull=False, network__isnull=True)
                                   | models.Q(social_account__isnull=True, network__isnull=False), name="favorite_one_target"),
            models.UniqueConstraint(fields=["user", "social_account"], condition=models.Q(social_account__isnull=False), name="fav_account_unique"),
            models.UniqueConstraint(fields=["user", "network"], condition=models.Q(network__isnull=False), name="fav_network_unique"),
        ]


class ViewedOffer(BaseModel):
    """Last time a user opened an offer card (one row per user/account, updated on revisit)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="viewed")
    social_account = models.ForeignKey("social_data.SocialAccount", on_delete=models.CASCADE, related_name="+")
    viewed_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "social_account"], name="viewed_unique")]
        indexes = [models.Index(fields=["user", "-viewed_at"])]


class PublicationMetric(BaseModel):
    """Result report checkpoint (D-018): at most three one-off checks per order item, only if the buyer opted in."""

    class Checkpoint(models.TextChoices):
        H24 = "24h", "Через 24 часа"
        D7 = "7d", "Через 7 дней"
        D30 = "30d", "Через 30 дней"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        DONE = "done", "Получено"
        UNAVAILABLE = "unavailable", "Недоступно"
        SKIPPED = "skipped", "Пропущено"

    order_item = models.ForeignKey("orders.OrderItem", on_delete=models.CASCADE, related_name="metrics")
    checkpoint = models.CharField(max_length=4, choices=Checkpoint.choices)
    due_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    views = models.PositiveBigIntegerField(null=True, blank=True)
    likes = models.PositiveBigIntegerField(null=True, blank=True)
    comments = models.PositiveBigIntegerField(null=True, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order_item", "checkpoint"], name="metric_checkpoint_unique")]
        indexes = [models.Index(fields=["status", "due_at"])]


class ReferralCode(BaseModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_code")
    code = models.CharField(max_length=16, unique=True)


class Referral(BaseModel):
    """Attribution only. Rewards need a funding decision (Q-10): there is no internal balance (roadmap 7.5)."""

    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referrals")
    referred = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referred_by")

    class Meta:
        constraints = [models.CheckConstraint(condition=~models.Q(referrer=models.F("referred")), name="no_self_referral")]

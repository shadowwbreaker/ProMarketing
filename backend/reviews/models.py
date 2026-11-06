from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.models import BaseModel


class Review(BaseModel):
    class Moderation(models.TextChoices):
        PUBLISHED = "published", "Опубликован"
        HIDDEN = "hidden", "Скрыт модератором"
        WITHDRAWN = "withdrawn", "Снят (заказ возвращён)"

    order_item = models.ForeignKey("orders.OrderItem", on_delete=models.PROTECT, related_name="reviews")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews_written")
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews_received")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField(blank=True, max_length=4000)
    seller_reply = models.TextField(blank=True, max_length=4000)
    moderation_status = models.CharField(max_length=16, choices=Moderation.choices, default=Moderation.PUBLISHED)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order_item", "author"], name="one_review_per_item_author"),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="review_rating_range"),
        ]


class ReviewComplaint(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Открыта"
        ACCEPTED = "accepted", "Принята"
        REJECTED = "rejected", "Отклонена"

    review = models.ForeignKey(Review, on_delete=models.PROTECT, related_name="complaints")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    reason = models.TextField(max_length=2000)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)

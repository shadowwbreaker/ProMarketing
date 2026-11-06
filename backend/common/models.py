import uuid

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """UUID primary key + timestamps for all domain tables."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionError("Append-only table: updates are forbidden")

    def delete(self):
        raise PermissionError("Append-only table: deletes are forbidden")


class AppendOnlyModel(models.Model):
    """Rows can be inserted but never changed or removed (D-011).

    Enforced at ORM level here and at database level by a trigger created in
    migrations (see common.db.append_only_trigger_sql).
    """

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("Append-only table: updates are forbidden")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Append-only table: deletes are forbidden")


CURRENCY_CHOICES = [("RUB", "RUB")]


class MoneyField(models.BigIntegerField):
    """Amount in minor units (kopecks). Never float (D-005)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("help_text", "Сумма в минимальных единицах валюты (копейках)")
        super().__init__(*args, **kwargs)

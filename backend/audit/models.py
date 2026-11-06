from django.conf import settings
from django.db import models

from common.models import AppendOnlyModel, BaseModel


class AuditLog(BaseModel, AppendOnlyModel):
    """Append-only, hash-chained log of significant actions (roadmap 9.9, D-011)."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    is_staff_action = models.BooleanField(default=False, db_index=True)
    action = models.CharField(max_length=64, db_index=True)
    subject_type = models.CharField(max_length=64)
    subject_id = models.CharField(max_length=64)
    order_id = models.UUIDField(null=True, blank=True, db_index=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    comment = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    seq = models.BigIntegerField(unique=True, editable=False)
    prev_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64, unique=True)

    class Meta:
        indexes = [models.Index(fields=["subject_type", "subject_id"])]
        ordering = ["seq"]


class AdminActionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_staff_action=True)


class AdminAction(AuditLog):
    """Staff actions view of the audit log (roadmap model list: AdminActions)."""

    objects = AdminActionManager()

    class Meta:
        proxy = True

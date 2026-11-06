from django.conf import settings
from django.db import models

from common.models import BaseModel


class Attachment(BaseModel):
    """Uploaded file metadata. Content lives in S3/MinIO under storage_key; sha256 proves integrity."""

    class ScanStatus(models.TextChoices):
        PENDING = "pending", "Ожидает проверки"
        CLEAN = "clean", "Проверен"
        REJECTED = "rejected", "Отклонён"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attachments")
    storage_key = models.CharField(max_length=512, unique=True)
    original_name = models.CharField(max_length=255)
    mime = models.CharField(max_length=127)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    scan_status = models.CharField(max_length=16, choices=ScanStatus.choices, default=ScanStatus.PENDING)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(size__gt=0), name="attachment_size_positive")]

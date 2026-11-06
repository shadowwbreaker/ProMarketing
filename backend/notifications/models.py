from django.conf import settings
from django.db import models

from common.models import BaseModel


class Notification(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=64)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, max_length=2000)
    payload = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "read_at", "-created_at"])]

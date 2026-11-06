from django.conf import settings
from django.db import models

from common.models import BaseModel


class Platform(models.TextChoices):
    TIKTOK = "tiktok", "TikTok"
    INSTAGRAM = "instagram", "Instagram Reels"
    YOUTUBE = "youtube", "YouTube Shorts"


class TrustStatus(models.TextChoices):
    """Statistics trust statuses (roadmap 3.8)."""

    VERIFIED = "VERIFIED", "Подтверждено"
    MANUAL = "MANUAL", "Введено вручную"
    STALE = "STALE", "Устарело"
    UNAVAILABLE = "UNAVAILABLE", "Недоступно"
    SUSPICIOUS = "SUSPICIOUS", "Подозрительно"
    ERROR = "ERROR", "Ошибка получения"


class DataSource(models.TextChoices):
    OFFICIAL_API = "official_api", "Официальный API"
    MANUAL = "manual", "Ручной ввод"
    VENDOR = "vendor", "Лицензированный поставщик"
    FAKE = "fake", "Тестовый провайдер (dev)"


class SocialAccount(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активен"
        HIDDEN = "hidden", "Скрыт продавцом"
        UNDER_REVIEW = "under_review", "На проверке"
        BLOCKED = "blocked", "Заблокирован"
        REMOVED = "removed", "Удалён"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="social_accounts")
    platform = models.CharField(max_length=16, choices=Platform.choices)
    external_id = models.CharField(max_length=128, help_text="ID аккаунта на платформе")
    handle = models.CharField(max_length=128)
    profile_url = models.URLField(max_length=500)
    title = models.CharField(max_length=120)
    category = models.CharField(max_length=64, blank=True)
    language = models.CharField(max_length=8, blank=True, default="ru")
    geo = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True, max_length=4000)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_listed = models.BooleanField(default=False, help_text="Показывается в каталоге")
    ownership_verified = models.BooleanField(default=False, help_text="Владение подтверждено OAuth")
    current_statistics = models.ForeignKey(
        "SocialAccountStatistics", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    last_refresh_requested_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # One platform account cannot be listed twice by different sellers
            models.UniqueConstraint(fields=["platform", "external_id"], name="social_account_platform_external_unique"),
        ]
        indexes = [models.Index(fields=["owner", "platform"]), models.Index(fields=["is_listed", "status"])]

    def __str__(self):
        return f"{self.platform}:{self.handle}"


class SocialAccountConnection(BaseModel):
    """OAuth connection to the platform (D-003). Tokens are encrypted at rest."""

    social_account = models.OneToOneField(SocialAccount, on_delete=models.CASCADE, related_name="connection")
    oauth_scopes = models.CharField(max_length=500, blank=True)
    access_token_enc = models.TextField(blank=True)
    refresh_token_enc = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class StatsRefreshJob(BaseModel):
    """One on-demand statistics fetch cycle. Never scheduled (roadmap 3.1)."""

    class Status(models.TextChoices):
        QUEUED = "queued", "В очереди"
        RUNNING = "running", "Выполняется"
        SUCCEEDED = "succeeded", "Успешно"
        FAILED = "failed", "Ошибка"

    class Trigger(models.TextChoices):
        ACCOUNT_ADDED = "account_added", "Добавление аккаунта"
        USER_REFRESH = "user_refresh", "Кнопка «Обновить»"
        ADMIN_CHECK = "admin_check", "Проверка администратором"

    social_account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE, related_name="refresh_jobs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    trigger = models.CharField(max_length=16, choices=Trigger.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["social_account"],
                condition=models.Q(status__in=["queued", "running"]),
                name="one_active_refresh_job_per_account",
            )
        ]
        indexes = [models.Index(fields=["social_account", "-created_at"])]


class SocialAccountStatistics(BaseModel):
    """Snapshot of a successful (or manual) statistics fetch. History is kept forever (roadmap 3.5)."""

    social_account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE, related_name="statistics")
    job = models.OneToOneField(StatsRefreshJob, null=True, blank=True, on_delete=models.SET_NULL, related_name="result")
    followers = models.PositiveBigIntegerField()
    avg_views = models.PositiveBigIntegerField(null=True, blank=True)
    videos_in_sample = models.PositiveSmallIntegerField(default=0)
    source = models.CharField(max_length=16, choices=DataSource.choices)
    trust_status = models.CharField(max_length=16, choices=TrustStatus.choices)
    fetched_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True, help_text="После этой даты статистика STALE")
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["social_account", "-fetched_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(videos_in_sample__gte=0) & models.Q(videos_in_sample__lte=50),
                name="stats_sample_size_range",
            ),
            models.CheckConstraint(
                condition=(models.Q(videos_in_sample=0) & models.Q(avg_views__isnull=True))
                | models.Q(videos_in_sample__gt=0),
                name="stats_avg_requires_videos",
            ),
        ]


class SocialVideo(BaseModel):
    statistics = models.ForeignKey(SocialAccountStatistics, on_delete=models.CASCADE, related_name="videos")
    external_video_id = models.CharField(max_length=128)
    url = models.URLField(max_length=500)
    published_at = models.DateTimeField(null=True, blank=True)
    views = models.PositiveBigIntegerField()
    likes = models.PositiveBigIntegerField(null=True, blank=True)
    comments = models.PositiveBigIntegerField(null=True, blank=True)
    duration_s = models.PositiveIntegerField(null=True, blank=True)
    is_short_heuristic = models.BooleanField(default=False, help_text="Shorts определён по длительности (YouTube)")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["statistics", "external_video_id"], name="video_unique_per_snapshot")
        ]

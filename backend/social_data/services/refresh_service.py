"""On-demand statistics refresh (roadmap 3.2–3.5). One user action → one job → one fetch cycle.

There is no scheduler here and must never be: refresh only happens when the owner adds an account,
presses «Обновить статистику», or an admin checks an account in a dispute.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.services import record
from common.exceptions import DomainError, RateLimited
from social_data.core import errors
from social_data.core.registry import get_provider
from social_data.models import (
    DataSource,
    SocialAccount,
    SocialAccountStatistics,
    SocialVideo,
    StatsRefreshJob,
    TrustStatus,
)

logger = logging.getLogger(__name__)

SUSPICIOUS_FOLLOWER_GROWTH = 3.0  # x3 within one interval → signal for moderation (not an accusation)
SUSPICIOUS_VIEWS_GROWTH = 5.0


def average_views(views: list[int]) -> int | None:
    """Average = sum(views) / number of retrieved videos (roadmap 3.2). Integer floor; None if no videos."""
    if not views:
        return None
    if any(v < 0 for v in views):
        raise ValueError("negative views")
    return sum(views) // len(views)


@dataclass
class Credentials:
    access_token: str


def credentials_for(account: SocialAccount) -> Credentials | None:
    from common.crypto import decrypt

    conn = getattr(account, "connection", None)
    if not conn or conn.revoked_at or not conn.access_token_enc:
        return None
    return Credentials(access_token=decrypt(conn.access_token_enc))


def next_allowed_at(account: SocialAccount):
    if not account.last_refresh_requested_at:
        return None
    return account.last_refresh_requested_at + timedelta(hours=settings.STATS_REFRESH_INTERVAL_HOURS)


def request_refresh(account_id, *, user, trigger: str = StatsRefreshJob.Trigger.USER_REFRESH) -> StatsRefreshJob:
    """Validate limits and create exactly one job. Raises RateLimited / DomainError with a reason."""
    from social_data.tasks import run_refresh_job

    with transaction.atomic():
        account = SocialAccount.objects.select_for_update().get(pk=account_id)
        if trigger != StatsRefreshJob.Trigger.ADMIN_CHECK and account.owner_id != user.pk:
            raise DomainError("Нет доступа к аккаунту", code="forbidden", status_code=403)
        if account.status in (SocialAccount.Status.BLOCKED, SocialAccount.Status.REMOVED):
            raise DomainError("Аккаунт недоступен для обновления", code="account_unavailable")
        if StatsRefreshJob.objects.filter(social_account=account, status__in=["queued", "running"]).exists():
            raise DomainError("Обновление уже выполняется", code="refresh_in_progress")
        nxt = next_allowed_at(account)
        if trigger == StatsRefreshJob.Trigger.USER_REFRESH and nxt and nxt > timezone.now():
            raise RateLimited(
                "Обновлять статистику можно не чаще одного раза в "
                f"{settings.STATS_REFRESH_INTERVAL_HOURS} ч.",
                details={"next_allowed_at": nxt.isoformat()},
            )
        try:
            with transaction.atomic():
                job = StatsRefreshJob.objects.create(social_account=account, requested_by=user, trigger=trigger)
        except IntegrityError as e:  # partial unique index: one active job per account
            raise DomainError("Обновление уже выполняется", code="refresh_in_progress") from e
        if trigger != StatsRefreshJob.Trigger.ADMIN_CHECK:
            account.last_refresh_requested_at = timezone.now()
            account.save(update_fields=["last_refresh_requested_at", "updated_at"])
        record(action="stats.refresh_requested", subject_type="social_account", subject_id=account.pk, actor=user,
               is_staff_action=trigger == StatsRefreshJob.Trigger.ADMIN_CHECK, after={"job": str(job.pk), "trigger": trigger})
        transaction.on_commit(lambda: run_refresh_job.delay(str(job.pk)))
    return job


def _trust_status(source: str, account: SocialAccount, followers: int, avg: int | None) -> tuple[str, str]:
    if source == DataSource.MANUAL:
        return TrustStatus.MANUAL, ""
    prev = account.current_statistics
    if prev and prev.source != DataSource.MANUAL:
        if prev.followers and followers / max(prev.followers, 1) >= SUSPICIOUS_FOLLOWER_GROWTH:
            return TrustStatus.SUSPICIOUS, f"Рост подписчиков x{followers / prev.followers:.1f} с прошлого обновления"
        if prev.avg_views and avg and avg / max(prev.avg_views, 1) >= SUSPICIOUS_VIEWS_GROWTH:
            return TrustStatus.SUSPICIOUS, f"Рост средних просмотров x{avg / prev.avg_views:.1f} с прошлого обновления"
    return TrustStatus.VERIFIED, ""


def run_job(job_id) -> StatsRefreshJob:
    """Execute exactly one fetch cycle. Failure never deletes or overwrites previous statistics."""
    with transaction.atomic():
        job = StatsRefreshJob.objects.select_for_update().select_related("social_account").get(pk=job_id)
        if job.status != StatsRefreshJob.Status.QUEUED:
            return job  # idempotent: duplicate task delivery does nothing
        job.status = StatsRefreshJob.Status.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])
    account = job.social_account
    try:
        provider = get_provider(account.platform)
        from social_data.core.types import ResolvedAccount

        resolved = ResolvedAccount(platform=account.platform, external_id=account.external_id, handle=account.handle,
                                   profile_url=account.profile_url, title=account.title)
        result = provider.fetch(resolved, limit=settings.STATS_SAMPLE_SIZE, credentials=credentials_for(account))
    except errors.ProviderError as e:
        return _fail(job, e.code, e.user_message)
    except Exception as e:  # noqa: BLE001 — never leak, never crash the worker
        logger.exception("stats refresh crashed job=%s", job_id)
        return _fail(job, "internal_error", f"Внутренняя ошибка: {type(e).__name__}")

    views = [v.views for v in result.videos]
    avg = average_views(views)
    with transaction.atomic():
        account = SocialAccount.objects.select_for_update().get(pk=account.pk)
        trust, note = _trust_status(result.source, account, result.account.followers, avg)
        now = timezone.now()
        stats = SocialAccountStatistics.objects.create(
            social_account=account, job=job, followers=result.account.followers, avg_views=avg,
            videos_in_sample=len(views), source=result.source, trust_status=trust, fetched_at=now,
            expires_at=now + timedelta(days=settings.STATS_STALE_AFTER_DAYS), notes=note,
        )
        SocialVideo.objects.bulk_create([
            SocialVideo(statistics=stats, external_video_id=v.external_id, url=v.url, published_at=v.published_at,
                        views=v.views, likes=v.likes, comments=v.comments, duration_s=v.duration_s,
                        is_short_heuristic=v.is_short_heuristic)
            for v in result.videos
        ])
        account.current_statistics = stats
        if trust == TrustStatus.SUSPICIOUS and account.status == SocialAccount.Status.ACTIVE:
            account.status = SocialAccount.Status.UNDER_REVIEW  # hidden until moderator check (scenario 8)
        account.save(update_fields=["current_statistics", "status", "updated_at"])
        job.status = StatsRefreshJob.Status.SUCCEEDED
        job.finished_at = now
        job.save(update_fields=["status", "finished_at", "updated_at"])
        record(action="stats.refreshed", subject_type="social_account", subject_id=account.pk,
               after={"followers": stats.followers, "avg_views": avg, "videos": len(views), "trust": trust})
    return job


def _fail(job: StatsRefreshJob, code: str, message: str) -> StatsRefreshJob:
    job.status = StatsRefreshJob.Status.FAILED
    job.error_code = code
    job.error_message = message
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error_code", "error_message", "finished_at", "updated_at"])
    record(action="stats.refresh_failed", subject_type="social_account", subject_id=job.social_account_id,
           after={"job": str(job.pk), "error": code})
    return job


@transaction.atomic
def save_manual_statistics(account: SocialAccount, *, user, followers: int, video_views: list[int]) -> SocialAccountStatistics:
    """Owner-entered numbers. Always MANUAL, never VERIFIED (roadmap 3.7)."""
    if account.owner_id != user.pk:
        raise DomainError("Нет доступа к аккаунту", code="forbidden", status_code=403)
    if followers < 0 or any(v < 0 for v in video_views) or len(video_views) > settings.STATS_SAMPLE_SIZE:
        raise DomainError("Некорректные значения статистики", code="invalid_manual_stats", status_code=400)
    now = timezone.now()
    stats = SocialAccountStatistics.objects.create(
        social_account=account, followers=followers, avg_views=average_views(video_views), videos_in_sample=len(video_views),
        source=DataSource.MANUAL, trust_status=TrustStatus.MANUAL, fetched_at=now,
        expires_at=now + timedelta(days=settings.STATS_STALE_AFTER_DAYS), notes="Введено владельцем вручную",
    )
    account.current_statistics = stats
    account.save(update_fields=["current_statistics", "updated_at"])
    record(action="stats.manual_entered", subject_type="social_account", subject_id=account.pk, actor=user,
           after={"followers": followers, "videos": len(video_views)})
    return stats


def display_status(stats: SocialAccountStatistics | None, platform: str, *, for_owner: bool) -> dict:
    """What a viewer may see (D-016 for YouTube; STALE by age)."""
    if stats is None:
        return {"trust_status": TrustStatus.UNAVAILABLE, "followers": None, "avg_views": None, "videos_in_sample": 0,
                "fetched_at": None, "source": None}
    status = stats.trust_status
    if stats.expires_at and stats.expires_at < timezone.now() and status in (TrustStatus.VERIFIED, TrustStatus.MANUAL):
        status = TrustStatus.STALE
    data = {"trust_status": status, "followers": stats.followers, "avg_views": stats.avg_views,
            "videos_in_sample": stats.videos_in_sample, "fetched_at": stats.fetched_at, "source": stats.source}
    if platform == "youtube" and not settings.YOUTUBE_DERIVED_METRICS_APPROVED and stats.source != DataSource.MANUAL:
        if not for_owner:  # followers stay verified; only the derived average is hidden from third parties
            data.update(avg_views=None)
        data["derived_metrics_note"] = "Среднее просмотров YouTube покупатели увидят после одобрения YouTube; подписчики подтверждены"  # D-016
    return data

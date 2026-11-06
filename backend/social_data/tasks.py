from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task(name="social_data.tasks.run_refresh_job")
def run_refresh_job(job_id: str):
    """One on-demand fetch cycle. Created only by social_data.services.refresh_service.request_refresh."""
    from social_data.services.refresh_service import run_job

    run_job(job_id)


@shared_task(name="social_data.tasks.purge_expired_youtube_data")
def purge_expired_youtube_data():
    """YouTube API policy: without derived-metrics approval, stored statistics older than 30 days must be
    deleted (D-016). DELETION ONLY — this task never calls YouTube."""
    from django.conf import settings

    from social_data.models import SocialAccountStatistics

    if settings.YOUTUBE_DERIVED_METRICS_APPROVED:
        return 0
    cutoff = timezone.now() - timedelta(days=30)
    qs = SocialAccountStatistics.objects.filter(social_account__platform="youtube", fetched_at__lt=cutoff).exclude(source="manual")
    n = qs.count()
    qs.delete()  # SocialVideo rows cascade; account.current_statistics is SET_NULL
    return n

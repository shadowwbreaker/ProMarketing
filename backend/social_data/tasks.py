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
    """Keep the 30-day retention window independently of public display. This task never calls YouTube."""
    from social_data.models import SocialAccountStatistics

    cutoff = timezone.now() - timedelta(days=30)
    qs = SocialAccountStatistics.objects.filter(social_account__platform="youtube", fetched_at__lt=cutoff).exclude(source="manual")
    n = qs.count()
    qs.delete()  # SocialVideo rows cascade; account.current_statistics is SET_NULL
    return n

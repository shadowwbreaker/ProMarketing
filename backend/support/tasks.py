from celery import shared_task


@shared_task(name="support.tasks.process_dispute_timeouts")
def process_dispute_timeouts():
    from .services import process_timeouts

    return process_timeouts()


@shared_task(name="support.tasks.close_expired_appeal_windows")
def close_expired_appeal_windows():
    from .services import close_expired_appeal_windows as run

    return run()

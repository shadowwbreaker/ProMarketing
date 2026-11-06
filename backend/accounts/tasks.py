from celery import shared_task


@shared_task(name="accounts.tasks.expire_sanctions")
def expire_sanctions():
    from .services import expire_sanctions as run

    return run()

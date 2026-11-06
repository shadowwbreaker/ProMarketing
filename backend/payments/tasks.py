from celery import shared_task


@shared_task(name="payments.tasks.release_payouts")
def release_payouts():
    from .services import release_payouts as run

    return run()

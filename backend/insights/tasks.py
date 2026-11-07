from celery import shared_task


@shared_task(name="insights.tasks.collect_due_metrics")
def collect_due_metrics():
    """D-018: executes the pre-planned 24h/7d/30d checkpoints (max 3 per opted-in order item). Not monitoring."""
    from .services import collect_due_metrics as run

    return run()

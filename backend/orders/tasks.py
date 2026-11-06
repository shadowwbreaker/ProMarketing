from celery import shared_task
from django.db import transaction
from django.utils import timezone


@shared_task(name="orders.tasks.check_publication")
def check_publication(item_id: str, trigger: str, requested_by_id: str | None = None):
    """ONE availability check of one published video, triggered by a specific order event (D-010).
    Not monitoring: never rescheduled by itself."""
    from social_data.core import errors
    from social_data.core.registry import get_provider
    from social_data.services.refresh_service import credentials_for

    from .models import OrderItem, PublicationCheck
    from .models import OrderStatus as S

    item = OrderItem.objects.select_related("social_account").get(pk=item_id)
    proof = item.proofs.order_by("-created_at").first()
    if not proof:
        return None
    try:
        video = get_provider(item.social_account.platform).get_video_statistics(
            proof.video_url, credentials=credentials_for(item.social_account))
        result = PublicationCheck.Result.FOUND if video else PublicationCheck.Result.NOT_FOUND
        details = {"views": video.views} if video else {}
    except errors.ProviderError as e:
        result, details = PublicationCheck.Result.UNAVAILABLE, {"error": e.code}
    check = PublicationCheck.objects.create(order_item=item, trigger=trigger, result=result, details=details,
                                            requested_by_id=requested_by_id, checked_at=timezone.now())

    if trigger == PublicationCheck.Trigger.WINDOW_END:
        item.refresh_from_db()
        if item.status != S.AWAITING_BUYER_CONFIRMATION:
            return check.result
        if result == PublicationCheck.Result.FOUND:
            from .services import confirm_item

            confirm_item(item.order_id, item.pk, auto=True)
        else:
            from support.models import SupportTicket

            from .events import append_event
            from .models import Order

            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=item.order_id)
                append_event(order, "item.auto_confirm_blocked", item=item, check=result)
                if not SupportTicket.objects.filter(order=order, category="auto_confirm_check").exists():
                    SupportTicket.objects.create(author=order.seller, order=order, category="auto_confirm_check",
                                                 subject="Окно подтверждения истекло, публикация не найдена", priority="high")
    return check.result


@shared_task(name="orders.tasks.expire_unaccepted")
def expire_unaccepted():
    from .services import expire_unaccepted as run

    return run()


@shared_task(name="orders.tasks.process_confirmation_windows")
def process_confirmation_windows():
    from .services import process_confirmation_windows as run

    return run()


@shared_task(name="orders.tasks.notify_missed_publish_deadlines")
def notify_missed_publish_deadlines():
    from .services import notify_missed_publish_deadlines as run

    return run()


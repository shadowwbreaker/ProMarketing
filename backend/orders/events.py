from django.db import transaction

from common.hashchain import compute_hash

from .models import Order, OrderEvent

GENESIS = "0" * 64


SYSTEM_TEXT = {
    "order.created": "Заказ создан. Условия зафиксированы.",
    "item.paid": "Оплата получена платёжным провайдером.",
    "item.accepted": "Продавец принял заказ.",
    "item.declined_by_seller": "Продавец отказался от заказа. Деньги возвращаются покупателю.",
    "item.published": "Продавец отправил ссылку на публикацию.",
    "item.confirmed": "Покупатель подтвердил выполнение. Выплата продавцу через 48 часов, если не будет жалоб.",
    "item.auto_confirmed": "Окно подтверждения истекло, публикация доступна — заказ подтверждён автоматически.",
    "item.rework_requested": "Покупатель попросил исправить публикацию.",
    "item.cancelled_by_buyer": "Покупатель отменил заказ до принятия.",
    "item.expired_not_accepted": "Продавец не принял заказ вовремя. Деньги возвращаются.",
    "item.refunded": "Возврат выполнен.",
    "terms.proposed": "Предложено изменить условия заказа.",
    "terms.changed": "Условия заказа изменены по согласию сторон.",
    "materials.delivered": "Покупатель передал рекламные материалы.",
    "item.publish_deadline_missed": "Срок публикации истёк.",
    "dispute.opened": "Открыта жалоба. Переписка зафиксирована для арбитража.",
    "dispute.decided": "Администрация приняла решение по жалобе.",
}


def append_event(order: Order, type_: str, *, actor=None, item=None, from_status: str = "", to_status: str = "",
                 **payload) -> OrderEvent:
    """Append to the per-order hash chain. Caller must hold a lock on the order row (select_for_update)."""
    with transaction.atomic():
        last = OrderEvent.objects.filter(order=order).order_by("-seq").values("seq", "hash").first()
        seq = (last["seq"] + 1) if last else 1
        prev = last["hash"] if last else GENESIS
        data = {k: str(v) if v is not None else None for k, v in payload.items()}
        body = {"seq": seq, "type": type_, "item": str(item.pk) if item else None, "actor": str(actor.pk) if actor else None,
                "from": from_status, "to": to_status, "payload": data}
        ev = OrderEvent.objects.create(order=order, order_item=item, actor=actor, type=type_, from_status=from_status,
                                       to_status=to_status, payload=data, seq=seq, prev_hash=prev, hash=compute_hash(prev, body))
        if type_ in SYSTEM_TEXT:
            from chats.services import system_message

            label = f"{item.social_account.title}: " if item is not None and order.items.count() > 1 else ""
            system_message(order, label + SYSTEM_TEXT[type_])
        return ev


def verify_order_chain(order: Order) -> bool:
    prev = GENESIS
    for e in OrderEvent.objects.filter(order=order).order_by("seq"):
        body = {"seq": e.seq, "type": e.type, "item": str(e.order_item_id) if e.order_item_id else None,
                "actor": str(e.actor_id) if e.actor_id else None, "from": e.from_status, "to": e.to_status, "payload": e.payload}
        if e.prev_hash != prev or compute_hash(prev, body) != e.hash:
            return False
        prev = e.hash
    return True

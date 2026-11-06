"""Centralised order-item state machine (roadmap 6.2). Every status change goes through `transition`."""
from common.exceptions import InvalidTransition

from .models import OrderStatus as S

ITEM_TRANSITIONS: dict[str, set[str]] = {
    S.DRAFT: {S.AWAITING_PAYMENT, S.CANCELLED},
    S.AWAITING_PAYMENT: {S.PAID, S.CANCELLED, S.EXPIRED},
    S.PAID: {S.AWAITING_SELLER_ACCEPTANCE},
    S.AWAITING_SELLER_ACCEPTANCE: {S.IN_PROGRESS, S.CANCELLED, S.EXPIRED, S.DISPUTED, S.REFUND_PENDING, S.REFUNDED},
    S.IN_PROGRESS: {S.AWAITING_PUBLICATION, S.PUBLISHED, S.DISPUTED, S.REFUND_PENDING, S.REFUNDED, S.PARTIALLY_REFUNDED, S.COMPLETED},
    S.AWAITING_PUBLICATION: {S.PUBLISHED, S.IN_PROGRESS, S.DISPUTED, S.REFUND_PENDING, S.REFUNDED, S.PARTIALLY_REFUNDED},
    S.PUBLISHED: {S.AWAITING_BUYER_CONFIRMATION, S.DISPUTED},
    S.AWAITING_BUYER_CONFIRMATION: {S.COMPLETED, S.DISPUTED, S.IN_PROGRESS},
    S.COMPLETED: {S.DISPUTED},  # complaint during the 48h payout hold (D-014) or placement breach
    S.DISPUTED: {S.AWAITING_SELLER_ACCEPTANCE, S.IN_PROGRESS, S.AWAITING_PUBLICATION, S.AWAITING_BUYER_CONFIRMATION, S.COMPLETED,
                 S.REFUND_PENDING, S.REFUNDED, S.PARTIALLY_REFUNDED},
    S.CANCELLED: {S.REFUND_PENDING, S.REFUNDED},
    S.EXPIRED: {S.REFUND_PENDING, S.REFUNDED},
    S.REFUND_PENDING: {S.REFUNDED, S.PARTIALLY_REFUNDED, S.DISPUTED},
    S.PARTIALLY_REFUNDED: {S.COMPLETED, S.DISPUTED, S.REFUND_PENDING, S.REFUNDED},
    S.REFUNDED: set(),
}

TERMINAL = {S.COMPLETED, S.CANCELLED, S.REFUNDED, S.PARTIALLY_REFUNDED, S.EXPIRED}
WORK_STATUSES = {S.AWAITING_SELLER_ACCEPTANCE, S.IN_PROGRESS, S.AWAITING_PUBLICATION, S.PUBLISHED, S.AWAITING_BUYER_CONFIRMATION}

# For the aggregate order status: the earliest active stage wins
_STAGE_ORDER = [S.DRAFT, S.AWAITING_PAYMENT, S.PAID, S.AWAITING_SELLER_ACCEPTANCE, S.IN_PROGRESS, S.AWAITING_PUBLICATION,
                S.PUBLISHED, S.AWAITING_BUYER_CONFIRMATION]


def can_transition(src: str, dst: str) -> bool:
    return dst in ITEM_TRANSITIONS.get(src, set())


def check_transition(src: str, dst: str) -> None:
    if not can_transition(src, dst):
        raise InvalidTransition(f"Переход {src} → {dst} недопустим", details={"from": src, "to": dst})


def aggregate_status(item_statuses: list[str]) -> str:
    """Order status derived from its items (supports partial network fulfilment)."""
    st = set(item_statuses)
    if not st:
        return S.DRAFT
    if len(st) == 1:
        return st.pop()
    if S.DISPUTED in st:
        return S.DISPUTED
    if S.REFUND_PENDING in st:
        return S.REFUND_PENDING
    active = [s for s in _STAGE_ORDER if s in st]
    if active:
        return active[0]
    # all terminal and mixed
    if st & {S.COMPLETED, S.PARTIALLY_REFUNDED} and st & {S.REFUNDED, S.CANCELLED, S.EXPIRED, S.PARTIALLY_REFUNDED}:
        return S.PARTIALLY_REFUNDED
    if st <= {S.REFUNDED, S.CANCELLED, S.EXPIRED}:
        return S.REFUNDED if S.REFUNDED in st else S.CANCELLED
    return S.COMPLETED

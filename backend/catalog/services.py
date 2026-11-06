"""Seller-side management of offers, listings and networks (roadmap Phase 4)."""
from django.db import IntegrityError, transaction

from audit.services import record
from common.exceptions import DomainError
from social_data.core.registry import platform_enabled
from social_data.models import SocialAccount
from social_data.services.refresh_service import display_status

from .models import AccountNetwork, AdvertisingOffer, NetworkItem

ACTIVE_ORDER_STATUSES = [
    "AWAITING_PAYMENT", "PAID", "AWAITING_SELLER_ACCEPTANCE", "IN_PROGRESS", "AWAITING_PUBLICATION", "PUBLISHED",
    "AWAITING_BUYER_CONFIRMATION", "DISPUTED", "REFUND_PENDING",
]


def _own(obj_owner_id, user):
    if obj_owner_id != user.pk:
        raise DomainError("Нет доступа", code="forbidden", status_code=404)


def create_offer(account: SocialAccount, *, user, **data) -> AdvertisingOffer:
    _own(account.owner_id, user)
    if account.status in (SocialAccount.Status.REMOVED, SocialAccount.Status.BLOCKED):
        raise DomainError("Аккаунт недоступен", code="account_unavailable")
    try:
        with transaction.atomic():
            offer = AdvertisingOffer.objects.create(social_account=account, currency="RUB", **data)
    except IntegrityError as e:
        raise DomainError("Активное предложение с этим форматом уже есть", code="offer_format_exists", status_code=400) from e
    record(action="offer.created", subject_type="offer", subject_id=offer.pk, actor=user,
           after={"price_minor": offer.price_minor, "format": offer.ad_format})
    return offer


def update_offer(offer: AdvertisingOffer, *, user, **data) -> AdvertisingOffer:
    """Changing price affects only future orders: orders store their own price (scenario 9)."""
    _own(offer.social_account.owner_id, user)
    before = {k: getattr(offer, k) for k in data}
    for k, v in data.items():
        setattr(offer, k, v)
    try:
        with transaction.atomic():
            offer.save()
    except IntegrityError as e:
        raise DomainError("Активное предложение с этим форматом уже есть", code="offer_format_exists", status_code=400) from e
    record(action="offer.updated", subject_type="offer", subject_id=offer.pk, actor=user, before=before, after=data)
    if not offer.is_active:
        _auto_unlist_if_no_offers(offer.social_account)
    return offer


def _auto_unlist_if_no_offers(account: SocialAccount):
    if account.is_listed and not account.offers.filter(is_active=True).exists():
        account.is_listed = False
        account.save(update_fields=["is_listed", "updated_at"])


def set_listing(account: SocialAccount, *, user, listed: bool) -> SocialAccount:
    _own(account.owner_id, user)
    if listed:
        problems = []
        if not user.is_email_verified:
            problems.append("подтвердите email")
        if not platform_enabled(account.platform):
            problems.append("платформа недоступна на сервисе")
        if account.status != SocialAccount.Status.ACTIVE:
            problems.append("аккаунт на проверке или заблокирован" if account.status in ("under_review", "blocked") else "аккаунт скрыт или удалён")
        if account.current_statistics_id is None:
            problems.append("получите статистику или введите её вручную")
        if not account.offers.filter(is_active=True).exists():
            problems.append("добавьте хотя бы одно активное предложение")
        if problems:
            raise DomainError("Нельзя опубликовать: " + "; ".join(problems), code="listing_not_allowed", status_code=400,
                              details={"problems": problems})
    account.is_listed = listed
    account.save(update_fields=["is_listed", "updated_at"])
    record(action="social_account.listing", subject_type="social_account", subject_id=account.pk, actor=user, after={"listed": listed})
    return account


def remove_account(account: SocialAccount, *, user) -> SocialAccount:
    """Remove from catalog permanently (soft delete). Not allowed while orders are active."""
    _own(account.owner_id, user)
    if account.order_items.filter(status__in=ACTIVE_ORDER_STATUSES).exists():
        raise DomainError("По аккаунту есть активные заказы — завершите их перед удалением", code="active_orders")
    with transaction.atomic():
        account.status = SocialAccount.Status.REMOVED
        account.is_listed = False
        account.save(update_fields=["status", "is_listed", "updated_at"])
        account.offers.update(is_active=False)
        NetworkItem.objects.filter(social_account=account).delete()
    record(action="social_account.removed", subject_type="social_account", subject_id=account.pk, actor=user)
    return account


# --- networks -------------------------------------------------------------------------
def create_network(*, user, **data) -> AccountNetwork:
    net = AccountNetwork.objects.create(owner=user, currency="RUB", **data)
    record(action="network.created", subject_type="network", subject_id=net.pk, actor=user)
    return net


def update_network(net: AccountNetwork, *, user, **data) -> AccountNetwork:
    _own(net.owner_id, user)
    before = {k: getattr(net, k) for k in data}
    for k, v in data.items():
        setattr(net, k, v)
    net.save()
    record(action="network.updated", subject_type="network", subject_id=net.pk, actor=user, before=before, after=data)
    return net


def add_network_item(net: AccountNetwork, *, user, offer: AdvertisingOffer, price_minor: int | None = None) -> NetworkItem:
    _own(net.owner_id, user)
    account = offer.social_account
    if account.owner_id != user.pk:
        raise DomainError("В сетку можно добавить только свои аккаунты", code="not_own_account", status_code=400)
    if not offer.is_active or account.status != SocialAccount.Status.ACTIVE:
        raise DomainError("Предложение или аккаунт неактивны", code="offer_inactive", status_code=400)
    try:
        with transaction.atomic():
            item = NetworkItem.objects.create(network=net, social_account=account, offer=offer,
                                              price_minor=price_minor or offer.price_minor)
    except IntegrityError as e:
        raise DomainError("Аккаунт уже есть в сетке", code="already_in_network", status_code=400) from e
    record(action="network.item_added", subject_type="network", subject_id=net.pk, actor=user, after={"account": str(account.pk)})
    return item


def remove_network_item(item: NetworkItem, *, user) -> None:
    _own(item.network.owner_id, user)
    net_id = item.network_id
    item.delete()
    record(action="network.item_removed", subject_type="network", subject_id=net_id, actor=user)


def network_price(net: AccountNetwork) -> int:
    items_sum = sum(i.price_minor for i in net.items.all())
    return net.total_price_minor or items_sum


def network_stats(net: AccountNetwork, *, for_owner: bool) -> dict:
    """Aggregate statistics of the network (roadmap 4.4). Each account stays independent."""
    items = list(net.items.select_related("social_account__current_statistics"))
    followers = 0
    avg_sum = 0
    with_avg = 0
    verified = 0
    for it in items:
        acc = it.social_account
        st = display_status(acc.current_statistics, acc.platform, for_owner=for_owner)
        followers += st["followers"] or 0
        if st["avg_views"] is not None:
            avg_sum += st["avg_views"]
            with_avg += 1
        verified += st["trust_status"] == "VERIFIED"
    return {
        "accounts": len(items), "total_followers": followers,
        "total_avg_views": avg_sum, "accounts_with_avg": with_avg, "verified_accounts": verified,
        "items_price_minor": sum(i.price_minor for i in items), "price_minor": net.total_price_minor or sum(i.price_minor for i in items),
    }

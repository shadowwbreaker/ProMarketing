"""Ownership verification by a code placed in the public profile description (D-020).

The owner asks for a code, puts it into the channel description, and presses "check".
Exactly one official API call per check; checks are rate-limited. No monitoring.
"""
import secrets

from audit.services import record
from common.exceptions import DomainError
from social_data.core import errors
from social_data.core.registry import get_provider
from social_data.core.types import ResolvedAccount
from social_data.models import SocialAccount

SUPPORTED = {"youtube"}


def start(account: SocialAccount, *, user) -> str:
    if account.ownership_verified:
        raise DomainError("Владение уже подтверждено", code="already_verified", status_code=400)
    if account.platform not in SUPPORTED:
        raise DomainError("Для этой платформы владение подтверждается входом через платформу", code="ownership_unsupported",
                          status_code=400)
    if not account.ownership_code:
        account.ownership_code = "PM-" + secrets.token_hex(3).upper()
        account.save(update_fields=["ownership_code", "updated_at"])
        record(action="social_account.ownership_code", subject_type="social_account", subject_id=account.pk, actor=user)
    return account.ownership_code


def check(account: SocialAccount, *, user) -> bool:
    if account.ownership_verified:
        return True
    if not account.ownership_code:
        raise DomainError("Сначала получите код", code="no_code", status_code=400)
    resolved = ResolvedAccount(platform=account.platform, external_id=account.external_id, handle=account.handle,
                               profile_url=account.profile_url, title=account.title)
    try:
        found = get_provider(account.platform).profile_contains(resolved, account.ownership_code)
    except errors.ProviderError as e:
        raise DomainError(e.user_message, code=e.code, status_code=400) from e
    if found:
        account.ownership_verified = True
        account.ownership_code = ""
        account.save(update_fields=["ownership_verified", "ownership_code", "updated_at"])
    record(action="social_account.ownership_check", subject_type="social_account", subject_id=account.pk, actor=user,
           after={"verified": found})
    return found


def find_claimable(platform: str, external_id: str, user) -> SocialAccount | None:
    """An account someone else added without proof of ownership can be claimed by its real owner."""
    acc = SocialAccount.objects.filter(platform=platform, external_id=external_id).first()
    if acc and acc.owner_id != user.pk and not acc.ownership_verified and platform in SUPPORTED:
        return acc
    return None


def start_claim(account: SocialAccount, *, user) -> str:
    from django.db import IntegrityError, transaction

    from social_data.models import OwnershipClaim

    if account.owner_id == user.pk or account.ownership_verified or account.platform not in SUPPORTED:
        raise DomainError("Этот канал нельзя забрать", code="not_claimable", status_code=400)
    claim = OwnershipClaim.objects.filter(account=account, claimant=user, resolved_at__isnull=True).first()
    if not claim:
        try:
            with transaction.atomic():
                claim = OwnershipClaim.objects.create(account=account, claimant=user, code="PM-" + secrets.token_hex(3).upper())
        except IntegrityError:
            claim = OwnershipClaim.objects.get(account=account, claimant=user, resolved_at__isnull=True)
        record(action="social_account.claim_started", subject_type="social_account", subject_id=account.pk, actor=user)
    return claim.code


def check_claim(account: SocialAccount, *, user) -> bool:
    """On success the account moves to the claimant: unlisted, previous offers deactivated, previous owner notified."""
    from django.db import transaction
    from django.utils import timezone

    from catalog.services import ACTIVE_ORDER_STATUSES
    from notifications.services import notify
    from social_data.models import OwnershipClaim

    claim = OwnershipClaim.objects.filter(account=account, claimant=user, resolved_at__isnull=True).first()
    if not claim:
        raise DomainError("Сначала получите код", code="no_code", status_code=400)
    if account.ownership_verified:
        raise DomainError("Владение этим каналом уже подтверждено другим пользователем — обратитесь в поддержку",
                          code="already_verified", status_code=400)
    resolved = ResolvedAccount(platform=account.platform, external_id=account.external_id, handle=account.handle,
                               profile_url=account.profile_url, title=account.title)
    try:
        found = get_provider(account.platform).profile_contains(resolved, claim.code)
    except errors.ProviderError as e:
        raise DomainError(e.user_message, code=e.code, status_code=400) from e
    record(action="social_account.claim_check", subject_type="social_account", subject_id=account.pk, actor=user,
           after={"found": found})
    if not found:
        return False
    if account.order_items.filter(status__in=ACTIVE_ORDER_STATUSES).exists():
        raise DomainError("По каналу идут заказы — передача после их завершения, напишите в поддержку",
                          code="active_orders", status_code=400)
    with transaction.atomic():
        previous = account.owner
        account.offers.filter(is_active=True).update(is_active=False)
        from catalog.models import NetworkItem

        NetworkItem.objects.filter(social_account=account).delete()  # drop it from the previous owner's networks
        account.owner = user
        account.ownership_verified = True
        account.ownership_code = ""
        account.is_listed = False
        account.status = SocialAccount.Status.ACTIVE
        account.save(update_fields=["owner", "ownership_verified", "ownership_code", "is_listed", "status", "updated_at"])
        OwnershipClaim.objects.filter(account=account, resolved_at__isnull=True).update(resolved_at=timezone.now())
        record(action="social_account.claimed", subject_type="social_account", subject_id=account.pk, actor=user,
               before={"owner": str(previous.pk)}, after={"owner": str(user.pk)})
        notify(previous, "account.claimed", "Канал передан владельцу",
               f"Владелец @{account.handle} подтвердил права на канал, он удалён из ваших объявлений.")
    return True

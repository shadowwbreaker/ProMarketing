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

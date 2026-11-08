"""Owner consent for fetching statistics (D-024). The text shown in the UI must match CONSENT_TEXT_VERSION."""
from common.exceptions import DomainError

CONSENT_TEXT_VERSION = "2026-11-09"
CONSENT_TEXT = (
    "Я владелец этого канала и разрешаю ProMarketing один раз получить из официального API платформы "
    "число подписчиков и просмотры последних 15 видео, чтобы показать их покупателям в объявлении. "
    "Повторно данные запрашиваются только когда я нажимаю «Обновить статистику»."
)


def require(data) -> None:
    if data.get("consent") is not True:
        raise DomainError("Подтвердите, что разрешаете получить статистику канала", code="consent_required", status_code=400)


def record_consent(*, user, request, platform: str, profile_url: str, purpose: str, account=None) -> None:
    from rest_framework.throttling import BaseThrottle

    from .models import StatsConsent

    StatsConsent.objects.create(user=user, account=account, platform=platform, profile_url=profile_url, purpose=purpose,
                                text_version=CONSENT_TEXT_VERSION, ip=BaseThrottle().get_ident(request))

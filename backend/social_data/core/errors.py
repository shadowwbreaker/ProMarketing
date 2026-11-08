class ProviderError(Exception):
    code = "provider_error"
    user_message = "Не удалось получить данные платформы"

    def __init__(self, message: str = "", *, user_message: str | None = None):
        super().__init__(message or self.user_message)
        if user_message:
            self.user_message = user_message


class InvalidProfileUrl(ProviderError):
    code = "invalid_profile_url"
    user_message = "Ссылка не похожа на профиль этой платформы"


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"
    user_message = "Сервис платформы временно недоступен"


class ProviderNotConfigured(ProviderError):
    code = "provider_not_configured"
    user_message = "Получение статистики для этой платформы пока не подключено"


class ProviderRateLimited(ProviderError):
    code = "provider_rate_limited"
    user_message = "Платформа ограничила число запросов, попробуйте позже"


class AuthorizationRequired(ProviderError):
    code = "authorization_required"
    user_message = "Нужно подключить канал через вход на платформе"


class AuthorizationExpired(ProviderError):
    code = "authorization_expired"
    user_message = "Доступ к каналу истёк, подключите канал заново"


class NotProfessionalAccount(ProviderError):
    code = "not_professional_account"
    user_message = "Нужен профессиональный (бизнес или автор) аккаунт"


class AccountNotFound(ProviderError):
    code = "account_not_found"
    user_message = "Канал не найден или недоступен"


class PlatformDisabled(ProviderError):
    code = "platform_disabled"
    user_message = "Платформа недоступна на сервисе"

"""RBAC matrix (D-012). Code checks permissions, never role names."""

ROLES = {
    "buyer": ("Покупатель", False),
    "seller": ("Продавец", False),
    "support_agent": ("Сотрудник поддержки", True),
    "moderator": ("Модератор", True),
    "admin": ("Администратор", True),
    "super_admin": ("Супер-администратор", True),
}

# Permission codes
P = {
    "order.create": "Создавать заказы",
    "account.manage_own": "Управлять своими рекламными аккаунтами",
    "dispute.open": "Открывать споры по своим заказам",
    "staff.access": "Доступ к служебному интерфейсу",
    "staff.view_orders": "Просмотр всех заказов",
    "staff.view_personal_data": "Просмотр персональных данных",
    "dispute.handle": "Рассматривать споры",
    "dispute.decide": "Принимать решения по спорам",
    "dispute.escalated": "Рассматривать эскалированные споры и апелляции",
    "finance.refund": "Инициировать возвраты",
    "finance.payout": "Управлять выплатами",
    "moderation.content": "Модерация предложений и отзывов",
    "moderation.stats": "Проверка подозрительной статистики",
    "user.sanction": "Применять санкции",
    "user.manage_roles": "Назначать роли",
    "settings.security": "Настройки безопасности платформы",
    "audit.view": "Просмотр журнала действий",
    "finance.view": "Просмотр финансовых показателей",
}

_BUYER = {"order.create", "dispute.open"}
_SELLER = {"account.manage_own", "dispute.open"}
_SUPPORT = {"staff.access", "staff.view_orders", "staff.view_personal_data", "dispute.handle"}
_MODERATOR = {"staff.access", "moderation.content", "moderation.stats"}
_ADMIN = _SUPPORT | _MODERATOR | {
    "dispute.decide",
    "dispute.escalated",
    "finance.refund",
    "finance.payout",
    "user.sanction",
    "audit.view",
    "finance.view",
}
_SUPER = _ADMIN | {"user.manage_roles", "settings.security"}

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "buyer": frozenset(_BUYER),
    "seller": frozenset(_SELLER),
    "support_agent": frozenset(_SUPPORT),
    "moderator": frozenset(_MODERATOR),
    "admin": frozenset(_ADMIN),
    "super_admin": frozenset(_SUPER),
}

assert all(p in P for perms in ROLE_PERMISSIONS.values() for p in perms)


def permissions_for_roles(role_codes) -> frozenset[str]:
    result: set[str] = set()
    for code in role_codes:
        result |= ROLE_PERMISSIONS.get(code, frozenset())
    return frozenset(result)


def assign_role(user, code: str, granted_by=None):
    from .models import Role, UserRole

    title, is_staff = ROLES[code]
    role, _ = Role.objects.get_or_create(code=code, defaults={"title": title, "is_staff_role": is_staff})
    UserRole.objects.get_or_create(user=user, role=role, defaults={"granted_by": granted_by})
    if hasattr(user, "_role_codes_cache"):
        del user._role_codes_cache
    return role

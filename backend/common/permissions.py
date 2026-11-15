from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsActiveUser(BasePermission):
    """Authenticated, active and not blocked."""

    message = "Доступ запрещён"

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated and u.is_active and u.status != u.Status.BLOCKED):
            return False
        if not getattr(view, "allow_before_staff_2fa", False):
            from accounts.twofactor import has_verified_session, is_enabled, required_for

            if required_for(u) and not has_verified_session(request, u):
                from common.exceptions import DomainError

                message = ("Войдите снова с кодом из приложения-аутентификатора" if is_enabled(u)
                           else "Включите двухфакторную защиту в профиле")
                raise DomainError(message, code="2fa_required", status_code=403)
        return True


def HasPerm(*codes: str):  # noqa: N802 — factory reads like a class in permission_classes
    """Permission class requiring ALL listed RBAC permission codes (D-012)."""

    class _HasPerm(IsActiveUser):
        message = "Недостаточно прав"

        def has_permission(self, request, view):
            if not super().has_permission(request, view):
                return False
            u = request.user
            if request.method in SAFE_METHODS and u.status == u.Status.LIMITED:
                from accounts.roles import permissions_for_roles

                return all(c in permissions_for_roles(u.role_codes) for c in codes)  # limited users can still read
            return all(u.has_perm_code(c) for c in codes)

    _HasPerm.__name__ = f"HasPerm({','.join(codes)})"
    return _HasPerm


class IsEmailVerified(IsActiveUser):
    """Actions with money or public listings require a confirmed email."""

    message = "Подтвердите email, чтобы выполнить это действие"

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_email_verified

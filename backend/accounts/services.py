import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from audit.services import record
from common.exceptions import DomainError

from .models import EmailToken, User, UserProfile
from .roles import ROLES, assign_role

TOKEN_TTL = {
    EmailToken.Purpose.VERIFY_EMAIL: timedelta(days=3),
    EmailToken.Purpose.RESET_PASSWORD: timedelta(hours=1),
}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(user: User, purpose: str) -> str:
    """Create a one-time token; only its hash is stored. Previous unused tokens of same purpose are invalidated."""
    now = timezone.now()
    EmailToken.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(used_at=now)
    token = secrets.token_urlsafe(32)
    EmailToken.objects.create(user=user, purpose=purpose, token_hash=_hash(token), expires_at=now + TOKEN_TTL[purpose])
    return token


def consume_token(token: str, purpose: str) -> User:
    with transaction.atomic():
        et = (
            EmailToken.objects.select_for_update()
            .select_related("user")
            .filter(token_hash=_hash(token or ""), purpose=purpose)
            .first()
        )
        if not et or et.used_at or et.expires_at < timezone.now():
            raise DomainError("Ссылка недействительна или устарела", code="invalid_token", status_code=400)
        et.used_at = timezone.now()
        et.save(update_fields=["used_at", "updated_at"])
        return et.user


def send_verification_email(user: User) -> None:
    token = issue_token(user, EmailToken.Purpose.VERIFY_EMAIL)
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    send_mail("Подтвердите email на ProMarketing", f"Подтвердите адрес: {link}", None, [user.email])


@transaction.atomic
def register_user(*, email: str, password: str, display_name: str, as_seller: bool = False) -> User:
    email = email.strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise DomainError("Пользователь с таким email уже существует", code="email_taken", status_code=400)
    candidate = User(email=email)
    validate_password(password, user=candidate)
    user = User.objects.create_user(email=email, password=password)
    UserProfile.objects.create(user=user, display_name=display_name.strip())
    assign_role(user, "buyer")
    if as_seller:
        assign_role(user, "seller")
    record(action="user.registered", subject_type="user", subject_id=user.pk, actor=user, after={"as_seller": as_seller})
    transaction.on_commit(lambda: send_verification_email(user))
    return user


def verify_email(token: str) -> User:
    user = consume_token(token, EmailToken.Purpose.VERIFY_EMAIL)
    if not user.is_email_verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified", "updated_at"])
        record(action="user.email_verified", subject_type="user", subject_id=user.pk, actor=user)
    return user


def request_password_reset(email: str) -> None:
    """Always succeeds silently to avoid account enumeration."""
    user = User.objects.filter(email__iexact=(email or "").strip(), is_active=True).first()
    if not user or user.status == User.Status.BLOCKED:
        return
    token = issue_token(user, EmailToken.Purpose.RESET_PASSWORD)
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    send_mail("Сброс пароля ProMarketing", f"Чтобы задать новый пароль, перейдите по ссылке: {link}", None, [user.email])


def reset_password(token: str, new_password: str) -> User:
    with transaction.atomic():
        user = consume_token(token, EmailToken.Purpose.RESET_PASSWORD)
        validate_password(new_password, user=user)
        user.set_password(new_password)  # changes session auth hash → all existing sessions invalidated
        user.save(update_fields=["password", "updated_at"])
        record(action="user.password_reset", subject_type="user", subject_id=user.pk, actor=user)
    return user


def become_seller(user: User) -> None:
    if not user.has_role("seller"):
        assign_role(user, "seller")
        record(action="user.became_seller", subject_type="user", subject_id=user.pk, actor=user)


@transaction.atomic
def set_roles(*, target: User, roles: list[str], actor: User, comment: str) -> None:
    from .models import UserRole

    unknown = set(roles) - set(ROLES)
    if unknown:
        raise DomainError(f"Неизвестные роли: {', '.join(sorted(unknown))}", code="unknown_role", status_code=400)
    if target.pk == actor.pk and "super_admin" not in roles and actor.has_role("super_admin"):
        raise DomainError("Нельзя снять с себя роль супер-администратора", code="self_demotion", status_code=400)
    before = sorted(target.role_codes)
    UserRole.objects.filter(user=target).exclude(role__code__in=roles).delete()
    for r in roles:
        assign_role(target, r, granted_by=actor)
    target.is_staff = any(ROLES[r][1] for r in roles)
    target.save(update_fields=["is_staff", "updated_at"])
    if hasattr(target, "_role_codes_cache"):
        del target._role_codes_cache
    record(action="user.roles_changed", subject_type="user", subject_id=target.pk, actor=actor, is_staff_action=True,
           before={"roles": before}, after={"roles": sorted(roles)}, comment=comment)


def expire_sanctions(now=None) -> int:
    """Temporary limits/blocks end automatically when their term passes (internal timer)."""
    from .models import UserSanction

    now = now or timezone.now()
    n = 0
    for s in UserSanction.objects.filter(revoked_at__isnull=True, ends_at__lte=now, type__in=["limit", "block"]).select_related("user"):
        s.revoked_at = now
        s.save(update_fields=["revoked_at", "updated_at"])
        u = s.user
        still = UserSanction.objects.filter(user=u, revoked_at__isnull=True, type__in=["limit", "block"]).filter(
            models_q_active(now)).exists()
        if not still and u.status != User.Status.ACTIVE:
            before = u.status
            u.status = User.Status.ACTIVE
            u.save(update_fields=["status", "updated_at"])
            record(action="user.sanction_expired", subject_type="user", subject_id=u.pk, before={"status": before},
                   after={"status": "active"})
        n += 1
    return n


def models_q_active(now):
    from django.db.models import Q

    return Q(ends_at__isnull=True) | Q(ends_at__gt=now)

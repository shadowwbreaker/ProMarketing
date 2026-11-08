from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from common.models import BaseModel


LIMITED_DENY = {"order.create", "account.manage_own"}


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_email_verified", True)
        user = self._create(email, password, **extra)
        from .roles import assign_role

        assign_role(user, "super_admin")
        return user


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активен"
        LIMITED = "limited", "Ограничен"
        BLOCKED = "blocked", "Заблокирован"

    email = models.EmailField(max_length=254, unique=True)
    is_email_verified = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Доступ к служебной админке Django")
    last_seen_at = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="user_email_ci_unique")]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def role_codes(self) -> set[str]:
        if not hasattr(self, "_role_codes_cache"):
            self._role_codes_cache = set(self.user_roles.values_list("role__code", flat=True))
        return self._role_codes_cache

    def has_role(self, code: str) -> bool:
        return code in self.role_codes

    def has_perm_code(self, perm: str) -> bool:
        from .roles import permissions_for_roles

        if self.status == self.Status.BLOCKED or not self.is_active:
            return False
        if self.status == self.Status.LIMITED and perm in LIMITED_DENY:
            return False  # temporary restriction: no new deals or listings, existing ones can be finished
        return perm in permissions_for_roles(self.role_codes)


class UserProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=80)
    bio = models.TextField(blank=True, max_length=2000)
    country = models.CharField(max_length=2, blank=True, default="RU")
    language = models.CharField(max_length=8, blank=True, default="ru")
    timezone = models.CharField(max_length=64, default="Europe/Moscow")
    avatar_key = models.CharField(max_length=255, blank=True, default="", help_text="Ключ файла аватара в хранилище")
    avatar_updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.display_name


class Role(models.Model):
    """Roles are fixed codes; permissions per role live in accounts/roles.py (D-012)."""

    code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=64)
    is_staff_role = models.BooleanField(default=False)

    def __str__(self):
        return self.code


class UserRole(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="user_roles")
    granted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="user_role_unique")]


class UserSanction(BaseModel):
    class Type(models.TextChoices):
        WARNING = "warning", "Предупреждение"
        LIMIT = "limit", "Временное ограничение"
        BLOCK = "block", "Блокировка"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sanctions")
    type = models.CharField(max_length=16, choices=Type.choices)
    reason = models.TextField()
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    dispute = models.ForeignKey("support.Dispute", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        indexes = [models.Index(fields=["user", "ends_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=models.F("starts_at")),
                name="sanction_ends_after_start",
            )
        ]


class EmailToken(BaseModel):
    """One-time tokens for email verification and password reset (hash stored, not token)."""

    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Подтверждение email"
        RESET_PASSWORD = "reset_password", "Сброс пароля"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_tokens")
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose"])]


class TwoFactor(BaseModel):
    """TOTP second factor (RFC 6238). Secret encrypted at rest; last used time-step blocks code replay."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="two_factor")
    secret_enc = models.TextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_step = models.BigIntegerField(default=0)

"""Staff two-factor authentication (TOTP). Required for staff endpoints when STAFF_2FA_REQUIRED is on (production)."""
import time

import pyotp
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from audit.services import record
from common.crypto import decrypt, encrypt
from common.exceptions import DomainError

from .models import TwoFactor

ISSUER = "ProMarketing"


def is_enabled(user) -> bool:
    tf = getattr(user, "two_factor", None)
    return bool(tf and tf.confirmed_at)


def setup(user) -> dict:
    tf = TwoFactor.objects.filter(user=user).first()
    if tf and tf.confirmed_at:
        raise DomainError("Двухфакторная защита уже включена", code="2fa_already_enabled")
    secret = pyotp.random_base32()
    TwoFactor.objects.update_or_create(user=user, defaults={"secret_enc": encrypt(secret), "confirmed_at": None, "last_step": 0})
    return {"secret": secret, "otpauth_url": pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=ISSUER)}


def verify(user, code: str) -> bool:
    """Accepts the current or adjacent 30-second step; a step can be used only once (replay protection)."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    with transaction.atomic():
        tf = TwoFactor.objects.select_for_update().filter(user=user).first()
        if not tf:
            return False
        totp = pyotp.TOTP(decrypt(tf.secret_enc))
        now_step = int(time.time()) // 30
        for step in (now_step - 1, now_step, now_step + 1):
            if step > tf.last_step and totp.at(step * 30) == code:
                tf.last_step = step
                tf.save(update_fields=["last_step", "updated_at"])
                return True
    return False


def confirm(user, code: str):
    tf = TwoFactor.objects.filter(user=user).first()
    if not tf or tf.confirmed_at:
        raise DomainError("Сначала начните настройку", code="2fa_not_started")
    if not verify(user, code):
        raise DomainError("Неверный код", code="invalid_otp", status_code=400)
    TwoFactor.objects.filter(pk=tf.pk).update(confirmed_at=timezone.now())
    record(action="user.2fa_enabled", subject_type="user", subject_id=user.pk, actor=user)


def disable(user, code: str, password: str):
    if not user.check_password(password or "") or not verify(user, code):
        raise DomainError("Неверный пароль или код", code="invalid_otp", status_code=400)
    TwoFactor.objects.filter(user=user).delete()
    record(action="user.2fa_disabled", subject_type="user", subject_id=user.pk, actor=user)


def required_for(user) -> bool:
    return bool(getattr(settings, "STAFF_2FA_REQUIRED", False)) and user.has_perm_code("staff.access")

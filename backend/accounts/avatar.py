"""Profile photo: decoded and re-encoded server-side (strips metadata, defeats polyglot files), 256x256 JPEG."""
import io
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from audit.services import record
from common.exceptions import DomainError
from common.permissions import IsActiveUser

from .models import UserProfile

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000  # decompression-bomb guard
SIZE = 256


def avatar_url(profile: UserProfile) -> str | None:
    if not profile.avatar_key:
        return None
    v = int(profile.avatar_updated_at.timestamp()) if profile.avatar_updated_at else 0
    return f"/api/v1/users/{profile.user_id}/avatar?v={v}"


def process(data: bytes) -> bytes:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ("JPEG", "PNG", "WEBP"):
            raise DomainError("Допустимы JPG, PNG или WEBP", code="file_type_not_allowed", status_code=400)
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise DomainError("Не удалось прочитать изображение", code="bad_image", status_code=400) from e
    img = ImageOps.fit(img, (SIZE, SIZE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88, optimize=True)
    return out.getvalue()


class MyAvatar(APIView):
    permission_classes = [IsActiveUser]
    parser_classes = [MultiPartParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "avatar"

    def post(self, request):
        f = request.FILES.get("file")
        if not f or f.size <= 0 or f.size > MAX_BYTES:
            raise DomainError("Выберите изображение до 5 МБ", code="file_too_large", status_code=400)
        jpeg = process(f.read())
        profile = request.user.profile
        old = profile.avatar_key
        key = f"avatars/{request.user.pk}/{uuid.uuid4().hex}.jpg"
        default_storage.save(key, ContentFile(jpeg))
        profile.avatar_key, profile.avatar_updated_at = key, timezone.now()
        profile.save(update_fields=["avatar_key", "avatar_updated_at", "updated_at"])
        if old:
            default_storage.delete(old)
        record(action="user.avatar_changed", subject_type="user", subject_id=request.user.pk, actor=request.user)
        return Response({"avatar_url": avatar_url(profile)}, status=201)

    def delete(self, request):
        profile = request.user.profile
        if profile.avatar_key:
            default_storage.delete(profile.avatar_key)
            profile.avatar_key, profile.avatar_updated_at = "", timezone.now()
            profile.save(update_fields=["avatar_key", "avatar_updated_at", "updated_at"])
        return Response(status=204)


class UserAvatar(APIView):
    """Public: avatars are shown on public profiles and catalog cards."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, user_id):
        profile = get_object_or_404(UserProfile, user_id=user_id)
        if not profile.avatar_key or not default_storage.exists(profile.avatar_key):
            raise Http404
        resp = FileResponse(default_storage.open(profile.avatar_key, "rb"), content_type="image/jpeg")
        resp["X-Content-Type-Options"] = "nosniff"
        resp["Cache-Control"] = "public, max-age=86400"
        return resp

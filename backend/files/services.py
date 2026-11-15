"""Validate attachments before storage and serve them only to authorized participants."""
import hashlib
import logging
import uuid
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError

from common.exceptions import DomainError

from .models import Attachment
from .scanner import scan

MAX_SIZE = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000
IMAGE_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/gif": "GIF", "image/webp": "WEBP"}
SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
    (b"%PDF-", "application/pdf", "pdf"),
]
logger = logging.getLogger(__name__)


def sniff(head: bytes) -> tuple[str, str] | None:
    for signature, mime, extension in SIGNATURES:
        if head.startswith(signature):
            return mime, extension
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    if head[4:8] == b"ftyp":
        return "video/mp4", "mp4"
    return None


def normalize_image(data: bytes, mime: str) -> bytes:
    """Validate the decoder's format and rebuild a static raster without untrusted metadata."""
    image_format = IMAGE_FORMATS[mime]
    try:
        with Image.open(BytesIO(data), formats=[image_format]) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise DomainError("Слишком большое разрешение изображения", code="image_too_large", status_code=400)
            if getattr(image, "is_animated", False):
                if not settings.ATTACHMENT_CLAMAV_HOST:
                    raise DomainError("Сейчас доступны только статичные изображения",
                                      code="animated_file_unavailable", status_code=400)
                # Check every frame before allowing the original animated file through the scanner.
                if image.n_frames * image.width * image.height > MAX_IMAGE_PIXELS:
                    raise DomainError("Слишком большое изображение", code="image_too_large", status_code=400)
                for index in range(image.n_frames):
                    image.seek(index)
                    image.load()
                return data
            image = ImageOps.exif_transpose(image)
            mode = "RGBA" if image_format != "JPEG" and ("A" in image.getbands() or "transparency" in image.info) else "RGB"
            pixels = image.convert(mode)
            pixels.info.clear()
            output = BytesIO()
            pixels.save(output, format=image_format)
            return output.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError, EOFError) as exc:
        raise DomainError("Изображение повреждено или не соответствует формату", code="invalid_image", status_code=400) from exc


def store_upload(*, owner, uploaded) -> Attachment:
    limit = settings.ATTACHMENT_MAX_SIZE
    data = uploaded.read(limit + 1)
    if not data or len(data) > limit:
        raise DomainError(f"Файл пустой или больше {limit // (1024 * 1024)} МБ", code="file_too_large", status_code=400)
    kind = sniff(data[:16])
    if not kind:
        raise DomainError("Допустимы PNG, JPG, GIF и WEBP", code="file_type_not_allowed", status_code=400)
    mime, ext = kind
    if settings.ATTACHMENT_CLAMAV_HOST:
        scan(data)
    elif mime not in IMAGE_FORMATS:
        raise DomainError("PDF и MP4 временно недоступны. Используйте изображение или ссылку.",
                          code="file_scan_required", status_code=400)
    if mime in IMAGE_FORMATS:
        data = normalize_image(data, mime)
    if len(data) > limit:
        raise DomainError("После обработки изображение превышает допустимый размер", code="file_too_large", status_code=400)
    digest = hashlib.sha256(data).hexdigest()
    key = default_storage.save(f"attachments/{owner.pk}/{uuid.uuid4().hex}.{ext}", ContentFile(data))
    name = (getattr(uploaded, "name", "") or f"file.{ext}").replace("/", "_").replace("\\", "_")[:200]
    try:
        return Attachment.objects.create(owner=owner, storage_key=key, original_name=name, mime=mime,
                                         size=len(data), sha256=digest, scan_status=Attachment.ScanStatus.CLEAN)
    except Exception:
        try:
            default_storage.delete(key)
        except OSError:
            logger.warning("Could not discard an orphaned attachment")
        raise


def can_read(user, att: Attachment) -> bool:
    if att.owner_id == user.pk or user.has_perm_code("staff.view_orders"):
        return True
    from chats.models import ChatMessage

    msg = ChatMessage.objects.filter(attachments=att).select_related("chat__order").first()
    if msg and user.pk in (msg.chat.order.buyer_id, msg.chat.order.seller_id):
        return True
    from support.models import DisputeEvidence

    ev = DisputeEvidence.objects.filter(attachment=att).select_related("dispute__order").first()
    return bool(ev and user.pk in (ev.dispute.order.buyer_id, ev.dispute.order.seller_id))

"""Attachment storage with type/size checks and integrity hash (roadmap 8.1, Phase 12 file checks).

Content is stored through Django's default storage (local MEDIA_ROOT in dev; S3/MinIO in production via
STORAGES setting). The real type is detected from file signature, not from the client's name or header.
"""
import hashlib
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from common.exceptions import DomainError

from .models import Attachment

MAX_SIZE = 20 * 1024 * 1024
SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
    (b"%PDF-", "application/pdf", "pdf"),
]


def sniff(head: bytes) -> tuple[str, str] | None:
    for sig, mime, ext in SIGNATURES:
        if head.startswith(sig):
            return mime, ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    if head[4:8] == b"ftyp":
        return "video/mp4", "mp4"
    return None


def store_upload(*, owner, uploaded) -> Attachment:
    size = uploaded.size
    limit = getattr(settings, "ATTACHMENT_MAX_SIZE", MAX_SIZE)
    if size <= 0 or size > limit:
        raise DomainError(f"Файл пустой или больше {limit // (1024 * 1024)} МБ", code="file_too_large", status_code=400)
    data = uploaded.read()
    kind = sniff(data[:16])
    if not kind:
        raise DomainError("Допустимы изображения (PNG, JPG, GIF, WEBP), PDF и MP4", code="file_type_not_allowed", status_code=400)
    mime, ext = kind
    digest = hashlib.sha256(data).hexdigest()
    key = f"attachments/{owner.pk}/{uuid.uuid4().hex}.{ext}"
    default_storage.save(key, ContentFile(data))
    name = (getattr(uploaded, "name", "") or f"file.{ext}").replace("/", "_").replace("\\", "_")[:200]
    # Scanning hook: images/PDF/MP4 that passed the signature check are marked clean here; an antivirus
    # scanner (Phase 12) can set REJECTED and the file is then never served.
    return Attachment.objects.create(owner=owner, storage_key=key, original_name=name, mime=mime, size=size, sha256=digest,
                                     scan_status=Attachment.ScanStatus.CLEAN)


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

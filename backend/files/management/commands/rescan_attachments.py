import hashlib

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from common.exceptions import DomainError
from files.models import Attachment
from files.scanner import scan
from files.services import IMAGE_FORMATS, normalize_image, sniff


class Command(BaseCommand):
    help = "Check quarantined attachments with ClamAV without changing their original content"

    def handle(self, *args, **options):
        if not settings.ATTACHMENT_CLAMAV_HOST:
            raise CommandError("Configure ATTACHMENT_CLAMAV_HOST on a private network first")
        pending = Attachment.objects.filter(scan_status=Attachment.ScanStatus.PENDING)
        counts = {"clean": 0, "rejected": 0, "unavailable": 0}
        for attachment in pending.iterator(chunk_size=100):
            try:
                with default_storage.open(attachment.storage_key, "rb") as file:
                    data = file.read(settings.ATTACHMENT_MAX_SIZE + 1)
            except OSError:
                counts["unavailable"] += 1
                continue
            kind = sniff(data[:16])
            verdict = Attachment.ScanStatus.REJECTED
            if (len(data) == attachment.size <= settings.ATTACHMENT_MAX_SIZE
                    and hashlib.sha256(data).hexdigest() == attachment.sha256
                    and kind and kind[0] == attachment.mime):
                try:
                    scan(data)
                    if attachment.mime in IMAGE_FORMATS:
                        normalize_image(data, attachment.mime)
                except DomainError as exc:
                    if exc.status_code == 503:
                        raise CommandError("Scanner unavailable. Remaining attachments are still quarantined.") from exc
                else:
                    verdict = Attachment.ScanStatus.CLEAN
            pending.filter(pk=attachment.pk).update(scan_status=verdict)
            counts[verdict] += 1
        self.stdout.write(" ".join(f"{status}={count}" for status, count in counts.items()))

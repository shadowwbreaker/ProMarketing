from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db import IntegrityError, transaction

from .models import StoredFile


class DatabaseStorage(Storage):
    def _open(self, name, mode="rb"):
        if mode != "rb":
            raise ValueError("DatabaseStorage supports binary reads only")
        try:
            data = StoredFile.objects.values_list("content", flat=True).get(pk=name)
        except StoredFile.DoesNotExist as exc:
            raise FileNotFoundError(name) from exc
        return ContentFile(bytes(data), name=name)

    def _save(self, name, content):
        data = b"".join(content.chunks())
        while True:
            try:
                with transaction.atomic():
                    StoredFile.objects.create(name=name, content=data)
            except IntegrityError:
                if not self.exists(name):
                    raise
                name = self.get_available_name(name, max_length=512)
            else:
                return name

    def exists(self, name):
        return StoredFile.objects.filter(pk=name).exists()

    def delete(self, name):
        StoredFile.objects.filter(pk=name).delete()

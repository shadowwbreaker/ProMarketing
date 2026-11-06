from django.core.files.storage import default_storage
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from common.exceptions import DomainError
from common.permissions import IsActiveUser

from .models import Attachment
from .services import can_read, store_upload


class UploadThrottle(UserRateThrottle):
    rate = "60/hour"


class Upload(APIView):
    permission_classes = [IsActiveUser]
    parser_classes = [MultiPartParser]
    throttle_classes = [UploadThrottle]

    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            raise DomainError("Файл не передан", code="no_file", status_code=400)
        a = store_upload(owner=request.user, uploaded=f)
        return Response({"id": str(a.pk), "name": a.original_name, "mime": a.mime, "size": a.size, "sha256": a.sha256}, status=201)


class Download(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, pk):
        a = get_object_or_404(Attachment, pk=pk, scan_status=Attachment.ScanStatus.CLEAN)
        if not can_read(request.user, a):
            raise DomainError("Нет доступа", code="forbidden", status_code=404)
        resp = FileResponse(default_storage.open(a.storage_key, "rb"), content_type=a.mime)
        resp["Content-Disposition"] = f'attachment; filename="{a.original_name}"'
        resp["X-Content-Type-Options"] = "nosniff"
        return resp

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

pytestmark = pytest.mark.django_db


def _png(w=600, h=400):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 50, 80)).save(buf, "PNG")
    return SimpleUploadedFile("me.png", buf.getvalue(), content_type="image/png")


def test_avatar_upload_is_reencoded_and_public(api, user_factory, settings, tmp_path):
    settings.STORAGES = {**settings.STORAGES, "default": {"BACKEND": "django.core.files.storage.FileSystemStorage",
                                                         "OPTIONS": {"location": str(tmp_path)}}}
    u = user_factory()
    api.force_authenticate(u)
    r = api.post("/api/v1/me/avatar", {"file": _png()}, format="multipart")
    assert r.status_code == 201, r.json()
    url = r.json()["avatar_url"]
    assert url.startswith(f"/api/v1/users/{u.pk}/avatar?v=")
    assert api.get("/api/v1/me").json()["profile"]["avatar_url"] == url
    api.force_authenticate(None)
    img = api.get(f"/api/v1/users/{u.pk}/avatar")
    assert img.status_code == 200 and img["Content-Type"] == "image/jpeg"
    data = b"".join(img.streaming_content)
    assert Image.open(io.BytesIO(data)).size == (256, 256)


def test_avatar_rejects_non_images(api, user_factory):
    u = user_factory()
    api.force_authenticate(u)
    bad = SimpleUploadedFile("x.png", b"%PDF-1.4 not an image", content_type="image/png")
    assert api.post("/api/v1/me/avatar", {"file": bad}, format="multipart").status_code == 400
    assert api.post("/api/v1/me/avatar", {}, format="multipart").status_code == 400
    assert api.get(f"/api/v1/users/{u.pk}/avatar").status_code == 404

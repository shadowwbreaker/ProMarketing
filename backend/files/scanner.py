"""ClamAV INSTREAM client. Only the exact success verdict can release a file."""
import socket
import struct

from django.conf import settings

from common.exceptions import DomainError


def scan(data: bytes) -> None:
    try:
        with socket.create_connection((settings.ATTACHMENT_CLAMAV_HOST, settings.ATTACHMENT_CLAMAV_PORT),
                                      timeout=settings.ATTACHMENT_SCAN_TIMEOUT) as connection:
            connection.sendall(b"zINSTREAM\0")
            for offset in range(0, len(data), 64 * 1024):
                chunk = data[offset:offset + 64 * 1024]
                connection.sendall(struct.pack("!I", len(chunk)) + chunk)
            connection.sendall(struct.pack("!I", 0))
            reply = bytearray()
            while len(reply) < 1024:
                chunk = connection.recv(1024 - len(reply))
                if not chunk:
                    break
                reply.extend(chunk)
                if b"\0" in chunk:
                    break
    except OSError as exc:
        raise DomainError("Проверка файлов временно недоступна", code="file_scan_unavailable", status_code=503) from exc
    if reply == b"stream: OK\0":
        return
    if reply.startswith(b"stream: ") and reply.endswith(b" FOUND\0"):
        raise DomainError("Файл отклонён при проверке безопасности", code="unsafe_file", status_code=400)
    raise DomainError("Проверка файлов временно недоступна", code="file_scan_unavailable", status_code=503)

import contextvars
import json
import logging
import re
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_SECRET_PATTERNS = [
    re.compile(r"(?i)(password|secret|token|authorization|api[_-]?key)(\"?\s*[:=]\s*\"?)([^\s\",]+)"),
]


def mask_secrets(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    return text


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": mask_secrets(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = mask_secrets(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)

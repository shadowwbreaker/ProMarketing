"""Unified API error format: {"error": {"code", "message", "details", "request_id"}}."""
import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .logging import request_id_var

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Business-rule violation raised by service layer."""

    code = "domain_error"
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


class InvalidTransition(DomainError):
    code = "invalid_transition"


class RateLimited(DomainError):
    code = "rate_limited"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


def _error(code: str, message: str, details, http_status: int) -> Response:
    return Response(
        {"error": {"code": code, "message": message, "details": details or {}, "request_id": request_id_var.get()}},
        status=http_status,
    )


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return _error(exc.code, exc.message, exc.details, exc.status_code)
    if isinstance(exc, DjangoValidationError):
        details = exc.message_dict if hasattr(exc, "error_dict") else {"non_field_errors": exc.messages}
        return _error("validation_error", "Ошибка валидации", details, 400)
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API error")
        return _error("server_error", "Внутренняя ошибка сервера", {}, 500)

    if isinstance(exc, exceptions.ValidationError):
        return _error("validation_error", "Ошибка валидации", response.data, response.status_code)
    code = getattr(exc, "default_code", "error")
    detail = response.data.get("detail", "") if isinstance(response.data, dict) else str(response.data)
    resp = _error(code, str(detail), {}, response.status_code)
    for header in ("Retry-After", "WWW-Authenticate"):
        if header in response:
            resp[header] = response[header]
    return resp

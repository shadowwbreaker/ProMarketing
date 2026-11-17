"""Atomic sliding-window throttles shared by all API workers."""
import logging
import math
import threading
import uuid

from django.core.cache import caches
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.redis import RedisCache
from rest_framework.throttling import AnonRateThrottle as DRFAnonRateThrottle
from rest_framework.throttling import ScopedRateThrottle as DRFScopedRateThrottle
from rest_framework.throttling import UserRateThrottle as DRFUserRateThrottle


logger = logging.getLogger(__name__)
_local_lock = threading.RLock()
_WINDOW = """
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
local duration = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - duration)
if redis.call('ZCARD', KEYS[1]) >= limit then
    local first = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return {0, math.max(1, math.ceil((tonumber(first[2]) + duration - now) * 1000))}
end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], math.ceil(duration * 1000))
return {1, 0}
"""


class AtomicWindow:
    def allow_request(self, request, view):
        if self.rate is None:
            return True
        key = self.get_cache_key(request, view)
        if key is None:
            return True
        backend = caches["default"]
        key = "rate:v2:" + key
        try:
            if isinstance(backend, RedisCache):
                client = backend._cache.get_client(key, write=True)
                allowed, wait_ms = client.eval(
                    _WINDOW, 1, backend.make_key(key), self.duration, self.num_requests, uuid.uuid4().hex,
                )
                self._retry_after = wait_ms / 1000
                return bool(allowed)
            if isinstance(backend, LocMemCache):
                # The test cache has no Lua. Serialize the entire read/check/write operation.
                with _local_lock:
                    now = self.timer()
                    history = [t for t in backend.get(key, []) if t > now - self.duration]
                    if len(history) >= self.num_requests:
                        self._retry_after = max(0.001, history[0] + self.duration - now)
                        return False
                    backend.set(key, [*history, now], timeout=math.ceil(self.duration))
                    self._retry_after = None
                    return True
            raise RuntimeError("Atomic throttling requires Redis")
        except Exception as exc:
            from common.exceptions import DomainError

            logger.warning("Rate limiter unavailable: %s", type(exc).__name__)
            raise DomainError("Сервис временно недоступен. Повторите запрос позже.",
                              code="rate_limit_unavailable", status_code=503) from exc

    def wait(self):
        return self._retry_after


class AnonRateThrottle(AtomicWindow, DRFAnonRateThrottle):
    pass


class UserRateThrottle(AtomicWindow, DRFUserRateThrottle):
    pass


class SignedInUserThrottle(UserRateThrottle):
    """Anonymous visitors use the per-IP limit, signed-in users their own limit."""

    def get_cache_key(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return None
        return super().get_cache_key(request, view)


class ScopedRateThrottle(AtomicWindow, DRFScopedRateThrottle):
    def allow_request(self, request, view):
        self.scope = getattr(view, self.scope_attr, None)
        if not self.scope:
            return True
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

"""Token-bucket rate limiter with pluggable backends.

Default backend is in-memory. Redis backend is optional and falls back to
in-memory automatically if Redis is unavailable at startup/runtime.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import HTTPException, Request

try:
    import redis
except Exception:  # pragma: no cover - optional dependency can be absent
    redis = None


class RateLimiterBackendError(RuntimeError):
    pass


class _Backend(Protocol):
    def check(self, key: str, route: str, per_minute: int, cost: float = 1.0) -> None: ...

    def reset(self) -> None: ...


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class _InMemoryBackend:
    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], _Bucket] = {}

    def check(self, key: str, route: str, per_minute: int, cost: float = 1.0) -> None:
        if per_minute <= 0:
            return
        rate = per_minute / 60.0
        capacity = float(per_minute)
        now = time.monotonic()
        b = self._buckets.get((key, route))
        if b is None:
            b = _Bucket(tokens=capacity, last_refill=now)
            self._buckets[(key, route)] = b
        else:
            elapsed = now - b.last_refill
            b.tokens = min(capacity, b.tokens + elapsed * rate)
            b.last_refill = now
        if b.tokens < cost:
            retry = max(1, int((cost - b.tokens) / rate))
            raise HTTPException(
                429,
                {"error": "rate_limited", "retry_after_seconds": retry},
                headers={"Retry-After": str(retry)},
            )
        b.tokens -= cost

    def reset(self) -> None:
        self._buckets.clear()


class _RedisBackend:
    _LUA = """
local now_ms = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local ttl_ms = tonumber(ARGV[5])

local current = redis.call('HMGET', KEYS[1], 'tokens', 'last')
local tokens = tonumber(current[1])
local last = tonumber(current[2])

if tokens == nil or last == nil then
  tokens = capacity
  last = now_ms
else
  local elapsed = (now_ms - last) / 1000.0
  tokens = math.min(capacity, tokens + elapsed * rate)
  last = now_ms
end

local allowed = 0
local retry = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry = math.max(1, math.ceil((cost - tokens) / rate))
end

redis.call('HMSET', KEYS[1], 'tokens', tokens, 'last', last)
redis.call('PEXPIRE', KEYS[1], ttl_ms)

return {allowed, retry}
"""

    def __init__(
        self,
        *,
        redis_url: str,
        prefix: str,
        ttl_seconds: int,
        redis_client: Any | None = None,
    ) -> None:
        if redis_client is not None:
            self._client = redis_client
        else:
            if redis is None:
                raise RateLimiterBackendError("redis dependency not installed")
            try:
                self._client = redis.Redis.from_url(redis_url, decode_responses=True)
                self._client.ping()
            except Exception as e:  # pragma: no cover - networked runtime path
                raise RateLimiterBackendError(f"redis init failed: {e}") from e
        self._prefix = prefix
        self._ttl_seconds = max(30, ttl_seconds)

    def _key(self, key: str, route: str) -> str:
        return f"{self._prefix}:{route}:{key}"

    def check(self, key: str, route: str, per_minute: int, cost: float = 1.0) -> None:
        if per_minute <= 0:
            return
        rate = per_minute / 60.0
        capacity = float(per_minute)
        now_ms = int(time.time() * 1000)
        ttl_ms = max(self._ttl_seconds * 1000, int((capacity / max(rate, 1e-6)) * 1000 * 2))
        redis_key = self._key(key, route)
        try:
            result = self._client.eval(
                self._LUA,
                1,
                redis_key,
                str(now_ms),
                str(rate),
                str(capacity),
                str(cost),
                str(ttl_ms),
            )
        except Exception as e:  # pragma: no cover - networked runtime path
            raise RateLimiterBackendError(f"redis check failed: {e}") from e

        if not isinstance(result, (list, tuple)) or len(result) < 2:
            raise RateLimiterBackendError("redis check failed: bad lua response")

        allowed = int(result[0])
        retry = int(result[1])
        if allowed != 1:
            raise HTTPException(
                429,
                {"error": "rate_limited", "retry_after_seconds": max(1, retry)},
                headers={"Retry-After": str(max(1, retry))},
            )

    def reset(self) -> None:
        # Best-effort test helper cleanup.
        try:
            keys = self._client.keys(f"{self._prefix}:*")
            if keys:
                self._client.delete(*keys)
        except Exception:
            return


class RateLimiter:
    def __init__(
        self,
        *,
        backend: str = "in_memory",
        redis_url: str = "",
        redis_prefix: str = "kt:rl",
        redis_ttl_seconds: int = 300,
        redis_client: Any | None = None,
    ) -> None:
        configured = (backend or "in_memory").strip().lower()
        self._configured_backend = configured
        self._fallback_backend: _Backend = _InMemoryBackend()
        self._backend: _Backend = self._fallback_backend
        self._active_backend = "in_memory"
        self._last_backend_error: str | None = None

        if configured == "redis":
            if not redis_url and redis_client is None:
                self._last_backend_error = "redis backend requested but KT_RL_REDIS_URL is unset"
                return
            try:
                self._backend = _RedisBackend(
                    redis_url=redis_url,
                    prefix=redis_prefix,
                    ttl_seconds=redis_ttl_seconds,
                    redis_client=redis_client,
                )
                self._active_backend = "redis"
            except RateLimiterBackendError as e:
                self._last_backend_error = str(e)
                self._backend = self._fallback_backend
                self._active_backend = "in_memory_fallback"

    @classmethod
    def from_settings(cls, settings: Any) -> RateLimiter:
        return cls(
            backend=getattr(settings, "rl_backend", "in_memory"),
            redis_url=getattr(settings, "rl_redis_url", ""),
            redis_prefix=getattr(settings, "rl_redis_prefix", "kt:rl"),
            redis_ttl_seconds=getattr(settings, "rl_redis_ttl_seconds", 300),
        )

    def check(self, key: str, route: str, per_minute: int, cost: float = 1.0) -> None:
        try:
            self._backend.check(key, route, per_minute, cost)
        except RateLimiterBackendError as e:
            self._last_backend_error = str(e)
            self._backend = self._fallback_backend
            self._active_backend = "in_memory_fallback"
            self._backend.check(key, route, per_minute, cost)

    def reset(self) -> None:
        self._backend.reset()
        self._fallback_backend.reset()

    def status(self) -> dict[str, str | None]:
        return {
            "configured_backend": self._configured_backend,
            "active_backend": self._active_backend,
            "last_backend_error": self._last_backend_error,
        }


def client_key(request: Request) -> str:
    """Key for rate-limit buckets: forwarded IP > direct IP."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return f"ip:{fwd.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"

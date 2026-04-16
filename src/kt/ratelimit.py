"""Tiny in-memory token-bucket per (key, route) limiter.

Single-process. If we ever scale horizontally, swap this for Redis-backed."""

from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class RateLimiter:
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


def client_key(request: Request) -> str:
    """Key for rate-limit buckets: authed user > forwarded IP > direct IP."""
    user = getattr(request.state, "user", None)
    if user and user.get("id"):
        return f"u:{user['id']}"
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return f"ip:{fwd.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"

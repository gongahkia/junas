import pytest
from fastapi import HTTPException

from kt.ratelimit import RateLimiter


def test_basic_token_bucket():
    rl = RateLimiter()
    for _ in range(5):
        rl.check("ip1", "r", 5)
    with pytest.raises(HTTPException) as exc:
        rl.check("ip1", "r", 5)
    assert exc.value.status_code == 429
    assert exc.value.detail["error"] == "rate_limited"


def test_separate_keys_independent():
    rl = RateLimiter()
    for _ in range(3):
        rl.check("a", "r", 3)
    rl.check("b", "r", 3)


def test_zero_disables():
    rl = RateLimiter()
    for _ in range(100):
        rl.check("ip", "r", 0)


async def test_create_session_rate_limited(client):
    body = {"host_display_name": "A", "provider": "tension"}
    seen_429 = False
    for _ in range(15):
        r = await client.post("/api/sessions", json=body)
        if r.status_code == 429:
            seen_429 = True
            break
    assert seen_429, "expected create_session to rate limit"


def test_redis_backend_without_url_falls_back_to_in_memory():
    rl = RateLimiter(backend="redis", redis_url="")
    status = rl.status()
    assert status["configured_backend"] == "redis"
    assert status["active_backend"] in {"in_memory", "in_memory_fallback"}
    assert status["last_backend_error"] is not None


class _BrokenRedis:
    def eval(self, *_args, **_kwargs):
        raise RuntimeError("redis down")


def test_redis_runtime_error_falls_back():
    rl = RateLimiter(
        backend="redis",
        redis_url="redis://example",
        redis_client=_BrokenRedis(),
    )
    # First call fails on Redis and then falls back to in-memory.
    rl.check("ip", "route", 5)
    status = rl.status()
    assert status["active_backend"] == "in_memory_fallback"
    assert status["last_backend_error"] is not None

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
    body = {"host_display_name": "A", "enabled_providers": []}
    seen_429 = False
    for _ in range(15):
        r = await client.post("/api/sessions", json=body)
        if r.status_code == 429:
            seen_429 = True
            break
    assert seen_429, "expected create_session to rate limit"

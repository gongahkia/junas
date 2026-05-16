from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient

from kt.config import Settings
from kt.main import create_app
from kt.security import CredentialCipher


async def test_readyz_reports_db_and_providers(client: AsyncClient):
    r = await client.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "ok"
    assert body["status"] == "ok"
    assert isinstance(body["providers"], dict)
    assert "tension" in body["providers"]
    assert body["rate_limiter_backend"] in {"in_memory", "in_memory_fallback", "redis"}
    assert "rate_limiter_configured_backend" in body


async def test_metrics_exposes_request_counts(client: AsyncClient):
    # Generate a few requests to populate counters
    for _ in range(3):
        await client.get("/api/v1/providers")
    m = await client.get("/metrics")
    assert m.status_code == 200
    body = m.text
    assert "kt_http_requests_total" in body
    assert 'route="/api/v1/providers"' in body
    assert "kt_http_request_duration_seconds" in body


async def test_gzip_applied_to_large_responses(client: AsyncClient):
    # /boards has enough payload to be gzipped (min 1024 bytes threshold).
    r = await client.get(
        "/api/v1/boards", headers={"Accept-Encoding": "gzip"}
    )
    assert r.status_code == 200
    # httpx decodes on the fly; check the server opted in via the header.
    assert r.headers.get("content-encoding") == "gzip"


def test_multifernet_supports_key_rotation():
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    old_cipher = CredentialCipher(old)
    ciphertext = old_cipher.encrypt({"username": "alex", "password": "pw"})

    # Rotated key list: new primary, old listed as legacy — decrypt still works.
    rotated = CredentialCipher(f"{new},{old}")
    assert rotated.decrypt(ciphertext) == {"username": "alex", "password": "pw"}

    # After rewrap, the ciphertext no longer decrypts with the old key alone.
    rewrapped = rotated.rewrap(ciphertext)
    assert rewrapped != ciphertext
    import pytest

    with pytest.raises(ValueError):
        old_cipher.decrypt(rewrapped)


def test_multifernet_single_key_still_works():
    key = Fernet.generate_key().decode()
    c = CredentialCipher(key)
    ct = c.encrypt({"x": 1})
    assert c.decrypt(ct) == {"x": 1}


@pytest.mark.asyncio
async def test_startup_fails_without_cred_key(tmp_path):
    app = create_app(Settings(db_path=tmp_path / "test.db", cred_key=""))
    with pytest.raises(RuntimeError, match="KT_CRED_KEY"):
        async with app.router.lifespan_context(app):
            pass

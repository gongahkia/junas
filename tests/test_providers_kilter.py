from __future__ import annotations

import httpx
import pytest

from kt.providers.base import (
    ClimbQuery,
    ProviderAuthError,
    ProviderStatus,
    ProviderUnavailable,
)
from kt.providers.kilter.client import KilterClient
from kt.providers.kilter.provider import KilterProvider


def test_marked_experimental():
    p = KilterProvider()
    assert p.status is ProviderStatus.EXPERIMENTAL
    assert p.requires_credentials


async def test_authenticate_without_client_id_fails_fast():
    # No KT_KILTER_CLIENT_ID, no client_id in payload -> ProviderAuthError
    p = KilterProvider(client=KilterClient(client_id=""))
    with pytest.raises(ProviderAuthError):
        await p.authenticate({"username": "u", "password": "p"})


async def test_authenticate_uses_keycloak_password_grant():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert "openid-connect/token" in str(req.url)
        body = dict(p.split("=", 1) for p in req.content.decode().split("&"))
        captured.update(body)
        return httpx.Response(200, json={"access_token": "atk_xyz", "expires_in": 300})

    client = KilterClient(client_id="kilter-mobile", transport=httpx.MockTransport(handler))
    p = KilterProvider(client=client)
    tok = await p.authenticate({"username": "u", "password": "p"})
    assert tok.value == "atk_xyz"
    assert captured["grant_type"] == "password"
    assert captured["client_id"] == "kilter-mobile"


async def test_authenticate_keycloak_rejection_is_auth_error():
    def handler(req): return httpx.Response(401, text="invalid_grant")
    client = KilterClient(client_id="cid", transport=httpx.MockTransport(handler))
    p = KilterProvider(client=client)
    with pytest.raises(ProviderAuthError):
        await p.authenticate({"username": "u", "password": "p"})


async def test_authenticate_upstream_5xx_is_unavailable():
    def handler(req): return httpx.Response(503)
    client = KilterClient(client_id="cid", transport=httpx.MockTransport(handler))
    p = KilterProvider(client=client)
    with pytest.raises(ProviderUnavailable):
        await p.authenticate({"username": "u", "password": "p"})


async def test_data_calls_still_unavailable_pending_powersync():
    p = KilterProvider()
    with pytest.raises(ProviderUnavailable):
        await p.list_layouts(None)
    with pytest.raises(ProviderUnavailable):
        await p.search_climbs(None, ClimbQuery())
    with pytest.raises(ProviderUnavailable):
        await p.get_climb(None, "x")

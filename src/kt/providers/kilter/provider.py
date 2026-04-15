from __future__ import annotations

from typing import Any

from kt.providers.base import (
    AuthToken,
    Climb,
    ClimbQuery,
    Layout,
    ProviderStatus,
    ProviderUnavailable,
)


class KilterProvider:
    """Experimental Kilter provider.

    Kilter split from Aurora on 2026-03-26 and moved to Keycloak OIDC + PowerSync.
    Until a stable client exists (tracking lemeryfertitta/BoardLib #78), this
    provider returns 503-equivalents so the rest of the backend stays healthy."""

    key = "kilter"
    name = "Kilter Board"
    status = ProviderStatus.EXPERIMENTAL
    requires_credentials = True

    def __init__(self, client: Any = None) -> None:
        from kt.providers.kilter.client import KilterClient

        self._client = client or KilterClient()

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken:
        token = await self._client.login(
            creds.get("username", ""), creds.get("password", "")
        )
        return AuthToken(provider=self.key, value=token)

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]:
        raise ProviderUnavailable("kilter provider is experimental; upstream migration in progress")

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        raise ProviderUnavailable("kilter provider is experimental; upstream migration in progress")

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        raise ProviderUnavailable("kilter provider is experimental; upstream migration in progress")

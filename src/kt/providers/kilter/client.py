from __future__ import annotations

from kt.providers.base import ProviderUnavailable


class KilterClient:
    """Placeholder for Keycloak OIDC + PowerSync client.

    The Kilter app post-2026-03 uses Keycloak for auth and PowerSync for data
    replication; there is no stable public endpoint surface to target yet."""

    async def login(self, username: str, password: str) -> str:
        raise ProviderUnavailable("kilter upstream not yet supported")

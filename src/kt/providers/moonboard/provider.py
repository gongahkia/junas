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


class MoonboardProvider:
    key = "moonboard"
    name = "MoonBoard"
    status = ProviderStatus.OK
    requires_credentials = True

    def __init__(self, scraper: Any = None) -> None:
        from kt.providers.moonboard.scraper import MoonboardScraper

        self._scraper = scraper or MoonboardScraper()

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken:
        username = creds.get("username") or ""
        password = creds.get("password") or ""
        session_cookie = await self._scraper.login(username, password)
        return AuthToken(provider=self.key, value=session_cookie)

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]:
        return [
            Layout(id="2016", name="MoonBoard 2016"),
            Layout(id="2019", name="MoonBoard 2019"),
            Layout(id="2024", name="MoonBoard 2024"),
        ]

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        if token is None:
            raise ProviderUnavailable("auth required")
        raw = await self._scraper.list_problems(
            session_cookie=token.value,
            layout_id=query.layout_id or "2019",
            text=query.text,
            limit=query.limit,
            offset=query.offset,
        )
        return [
            Climb(
                id=str(r.get("id")),
                provider=self.key,
                name=str(r.get("name", "")),
                setter=r.get("setter"),
                grade=r.get("grade"),
                angle=r.get("angle"),
                ascents=r.get("ascents"),
                holds=list(r.get("holds") or []),
            )
            for r in raw
        ]

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        climbs = await self.search_climbs(token, ClimbQuery(limit=1_000))
        for c in climbs:
            if c.id == climb_id:
                return c
        raise KeyError(climb_id)

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
    """MoonBoard provider — surfaces the host's own logbook entries.

    The MoonBoard website does not expose a public problems API; the mobile app
    uses different infrastructure. `search_climbs` therefore returns the host
    user's own logged ascents, which is still useful for queueing repeats."""

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
        page = (query.offset // max(1, query.limit)) + 1
        data, _total = await self._scraper.list_logbook(
            session_cookie=token.value, page=page, page_size=query.limit
        )
        climbs = [_to_climb(self.key, r) for r in data]
        if query.text:
            t = query.text.lower()
            climbs = [c for c in climbs if t in c.name.lower()]
        return climbs

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        for page in range(1, 50):
            data, _ = await self._scraper.list_logbook(token.value, page=page, page_size=50)
            if not data:
                break
            for r in data:
                if str(r.get("Id") or r.get("ProblemId")) == climb_id:
                    return _to_climb(self.key, r)
        raise KeyError(climb_id)


def _to_climb(provider: str, raw: dict[str, Any]) -> Climb:
    return Climb(
        id=str(raw.get("Id") or raw.get("ProblemId") or raw.get("id")),
        provider=provider,
        name=str(raw.get("Name") or raw.get("ProblemName") or ""),
        setter=raw.get("Setter") or raw.get("SetByUserName"),
        grade=raw.get("Grade") or raw.get("GradeName"),
        angle=raw.get("Angle"),
        ascents=raw.get("Repeats") or raw.get("Count"),
        extras={k: v for k, v in raw.items() if k not in {"Id", "Name", "ProblemName"}},
    )

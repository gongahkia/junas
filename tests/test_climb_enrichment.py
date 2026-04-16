from __future__ import annotations

import base64
import json

from httpx import AsyncClient

from kt.providers import registry
from kt.providers.base import AuthToken, Climb, ClimbQuery, ProviderStatus


class _FakeProvider:
    key = "fake"
    name = "Fake"
    status = ProviderStatus.OK
    requires_credentials = False

    def __init__(self, climbs: list[Climb]) -> None:
        self._climbs = climbs

    async def authenticate(self, creds):
        return AuthToken(provider=self.key, value="ok")

    async def list_layouts(self, token):
        return []

    async def search_climbs(self, token, query: ClimbQuery):
        return self._climbs[query.offset : query.offset + query.limit]

    async def get_climb(self, token, climb_id):
        for c in self._climbs:
            if c.id == climb_id:
                return c
        raise KeyError(climb_id)


async def _create_session(
    client: AsyncClient, provider_key: str
) -> tuple[str, dict[str, str]]:
    r = await client.post(
        "/api/v1/sessions",
        json={"host_display_name": "Host", "provider": provider_key},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    return payload["code"], {"X-Session-Read-Token": payload["session_read_token"]}


def _make_climbs(n: int = 30) -> list[Climb]:
    # Mix of grades/stars/ascents for sort tests.
    grades = ["V3", "V5", "7A", "7A+", "8A"]  # maps to 3, 5, 6, 7, 11
    out: list[Climb] = []
    for i in range(n):
        out.append(
            Climb(
                id=f"c{i}",
                provider="fake",
                name=f"Climb {i}",
                setter=f"setter{i % 3}",
                grade=grades[i % len(grades)],
                angle=40 + (i % 3) * 5,
                ascents=i * 2,
                holds=[f"H{i}"],
                extras={
                    "quality_average": (i % 5) * 0.5,
                    "image_url": f"https://cdn.example/{i}.jpg",
                    "tags": ["powerful", "crimps"] if i % 2 == 0 else [],
                },
            )
        )
    return out


async def test_climbs_are_enriched_with_grades_and_media(client: AsyncClient):
    climbs = _make_climbs(5)
    registry.register(_FakeProvider(climbs))
    try:
        code, read_headers = await _create_session(client, "fake")
        r = await client.get(
            f"/api/v1/sessions/{code}/climbs?limit=5", headers=read_headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["climbs"]) == 5
        first = body["climbs"][0]
        assert first["grades"]["v"] is not None
        assert first["grades"]["font"]
        assert first["grades"]["yds"]
        assert first["media"] and first["media"][0]["kind"] == "image"
        assert first["setter_ref"]["name"]
        assert first["stars"] is not None
    finally:
        registry._providers.pop("fake", None)  # type: ignore[attr-defined]


async def test_climbs_cursor_pagination_round_trips(client: AsyncClient):
    climbs = _make_climbs(20)
    registry.register(_FakeProvider(climbs))
    try:
        code, read_headers = await _create_session(client, "fake")
        page1 = await client.get(
            f"/api/v1/sessions/{code}/climbs?limit=5", headers=read_headers
        )
        ids1 = [c["id"] for c in page1.json()["climbs"]]
        assert len(ids1) == 5
        cursor = page1.json()["next_cursor"]

        decoded = json.loads(base64.urlsafe_b64decode(cursor + "==").decode())
        assert decoded["o"] == 5

        page2 = await client.get(
            f"/api/v1/sessions/{code}/climbs",
            params={"limit": 5, "cursor": cursor},
            headers=read_headers,
        )
        ids2 = [c["id"] for c in page2.json()["climbs"]]
        assert ids2 != ids1
        assert set(ids1).isdisjoint(ids2)
    finally:
        registry._providers.pop("fake", None)  # type: ignore[attr-defined]


async def test_climbs_grade_filter(client: AsyncClient):
    climbs = _make_climbs(30)
    registry.register(_FakeProvider(climbs))
    try:
        code, read_headers = await _create_session(client, "fake")
        r = await client.get(
            f"/api/v1/sessions/{code}/climbs",
            params={"limit": 10, "grade_min_v": 6, "grade_max_v": 11},
            headers=read_headers,
        )
        assert r.status_code == 200
        vs = [c["grades"]["v"] for c in r.json()["climbs"] if c["grades"]]
        assert vs
        assert all(6 <= v <= 11 for v in vs)
    finally:
        registry._providers.pop("fake", None)  # type: ignore[attr-defined]


async def test_climbs_sort_by_stars(client: AsyncClient):
    climbs = _make_climbs(10)
    registry.register(_FakeProvider(climbs))
    try:
        code, read_headers = await _create_session(client, "fake")
        r = await client.get(
            f"/api/v1/sessions/{code}/climbs",
            params={"limit": 10, "sort": "stars"},
            headers=read_headers,
        )
        assert r.status_code == 200
        starseq = [c["stars"] or 0 for c in r.json()["climbs"]]
        assert starseq == sorted(starseq, reverse=True)
    finally:
        registry._providers.pop("fake", None)  # type: ignore[attr-defined]


async def test_climbs_bad_cursor_returns_400(client: AsyncClient):
    climbs = _make_climbs(5)
    registry.register(_FakeProvider(climbs))
    try:
        code, read_headers = await _create_session(client, "fake")
        r = await client.get(
            f"/api/v1/sessions/{code}/climbs",
            params={"cursor": "not-a-real-cursor", "limit": 5},
            headers=read_headers,
        )
        assert r.status_code == 400
    finally:
        registry._providers.pop("fake", None)  # type: ignore[attr-defined]


async def test_climbs_bad_sort_returns_400(client: AsyncClient):
    climbs = _make_climbs(3)
    registry.register(_FakeProvider(climbs))
    try:
        code, read_headers = await _create_session(client, "fake")
        r = await client.get(
            f"/api/v1/sessions/{code}/climbs",
            params={"sort": "chaos"},
            headers=read_headers,
        )
        assert r.status_code == 400
    finally:
        registry._providers.pop("fake", None)  # type: ignore[attr-defined]

from importlib import resources

from kt.providers import registry
from kt.providers.base import AuthToken, Climb, ClimbQuery, Layout, ProviderStatus
from kt.providers.moonboard import static_catalog


def test_bundled_moonboard_catalog_resources_are_present():
    data_root = resources.files("kt.providers.moonboard.data")
    names = {path.name for path in data_root.iterdir()}
    assert {"benchmarks.json", "2016.json", "2017.json", "LICENSE"} <= names

    assert len(static_catalog.load_layout("benchmarks")) > 1_500
    assert len(static_catalog.load_layout("2016")) > 10_000
    assert len(static_catalog.load_layout("2017")) > 10_000


async def test_bundled_moonboard_catalog_is_served_over_api(client):
    create = await client.post(
        "/api/sessions",
        json={"host_display_name": "Alex", "provider": "moonboard_catalog"},
    )
    assert create.status_code == 200, create.text
    payload = create.json()
    code = payload["code"]
    read_headers = {"X-Session-Read-Token": payload["session_read_token"]}

    response = await client.get(
        f"/api/sessions/{code}/climbs",
        params={"layout_id": "2016", "limit": 25},
        headers=read_headers,
    )
    assert response.status_code == 200, response.text

    climbs = response.json()["climbs"]
    assert len(climbs) == 25
    assert {climb["provider"] for climb in climbs} == {"moonboard_catalog"}
    assert all(climb["id"] for climb in climbs)
    assert all(climb["name"] for climb in climbs)
    assert all(climb["grade"] for climb in climbs)
    assert all(isinstance(climb["holds"], list) for climb in climbs)
    assert all(climb["extras"]["layout"] == "2016" for climb in climbs)


async def test_multi_provider_session_aggregates_without_provider_query(client):
    create = await client.post(
        "/api/sessions",
        json={
            "host_display_name": "Alex",
            "enabled_providers": ["moonboard_catalog", "crux"],
        },
    )
    assert create.status_code == 200, create.text
    payload = create.json()
    code = payload["code"]
    read_headers = {"X-Session-Read-Token": payload["session_read_token"]}

    missing = await client.get(
        f"/api/sessions/{code}/climbs",
        params={"layout_id": "2016", "limit": 2},
        headers=read_headers,
    )
    assert missing.status_code == 200
    body = missing.json()
    assert "warnings" in body
    assert body["meta"]["provider"] == "multi"

    disabled = await client.get(
        f"/api/sessions/{code}/climbs",
        params={"provider": "tension"},
        headers=read_headers,
    )
    assert disabled.status_code == 400
    assert disabled.json()["detail"]["error"] == "provider_not_enabled"

    ok = await client.get(
        f"/api/sessions/{code}/climbs",
        params={"provider": "moonboard_catalog", "layout_id": "2016", "limit": 2},
        headers=read_headers,
    )
    assert ok.status_code == 200, ok.text
    assert len(ok.json()["climbs"]) == 2


async def test_layouts_endpoint_serves_and_caches_public_provider(client):
    create = await client.post(
        "/api/sessions",
        json={"host_display_name": "Alex", "provider": "moonboard_catalog"},
    )
    assert create.status_code == 200, create.text
    payload = create.json()
    code = payload["code"]
    read_headers = {"X-Session-Read-Token": payload["session_read_token"]}

    first = await client.get(f"/api/sessions/{code}/layouts", headers=read_headers)
    assert first.status_code == 200, first.text
    layouts = first.json()["layouts"]
    assert {layout["id"] for layout in layouts} >= {"benchmarks", "2016", "2017"}


class CountingProvider:
    key = "counting"
    name = "Counting"
    status = ProviderStatus.OK
    requires_credentials = False

    def __init__(self) -> None:
        self.search_calls = 0

    async def authenticate(self, creds):
        return AuthToken(provider=self.key, value="public")

    async def list_layouts(self, token):
        return [Layout(id="default", name="Default")]

    async def search_climbs(self, token, query: ClimbQuery):
        self.search_calls += 1
        return [
            Climb(
                id=f"c{self.search_calls}",
                provider=self.key,
                name="Cached",
                setter=None,
                grade=None,
                angle=None,
                ascents=None,
            )
        ]

    async def get_climb(self, token, climb_id):
        raise KeyError(climb_id)


async def test_climb_search_uses_session_scoped_cache(client):
    provider = CountingProvider()
    registry.register(provider)
    try:
        create = await client.post(
            "/api/sessions",
            json={"host_display_name": "Alex", "provider": "counting"},
        )
        assert create.status_code == 200, create.text
        payload = create.json()
        code = payload["code"]
        read_headers = {"X-Session-Read-Token": payload["session_read_token"]}

        first = await client.get(f"/api/sessions/{code}/climbs", headers=read_headers)
        second = await client.get(f"/api/sessions/{code}/climbs", headers=read_headers)

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert provider.search_calls == 1
        assert first.json()["climbs"] == second.json()["climbs"]
        assert first.json()["meta"]["cache"]["hit"] is False
        assert second.json()["meta"]["cache"]["hit"] is True
    finally:
        registry.bootstrap()

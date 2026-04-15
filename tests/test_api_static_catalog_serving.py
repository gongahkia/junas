from importlib import resources

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
    code = create.json()["code"]

    response = await client.get(
        f"/api/sessions/{code}/climbs",
        params={"layout_id": "2016", "limit": 25},
    )
    assert response.status_code == 200, response.text

    climbs = response.json()["climbs"]
    assert len(climbs) == 25
    assert {climb["provider"] for climb in climbs} == {"moonboard_catalog"}
    assert all(climb["id"] for climb in climbs)
    assert all(climb["name"] for climb in climbs)
    assert all(climb["grade"] for climb in climbs)

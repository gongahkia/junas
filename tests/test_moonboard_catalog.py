from kt.providers.base import ClimbQuery
from kt.providers.moonboard import static_catalog
from kt.providers.moonboard.catalog_provider import MoonboardCatalogProvider


def test_layouts_supported():
    layouts = static_catalog.supported_layouts()
    assert "benchmarks" in layouts
    assert "2016" in layouts
    assert "2017" in layouts


def test_benchmarks_have_real_metadata():
    rows = static_catalog.load_layout("benchmarks")
    assert len(rows) > 1500
    by_setter = next((r for r in rows if r["setter"] == "Ben Moon"), None)
    assert by_setter is not None
    assert by_setter["name"]
    assert by_setter["repeats"] is not None
    assert by_setter["start_holds"] and by_setter["end_holds"]


def test_search_benchmarks_by_setter():
    rows = static_catalog.search("benchmarks", text="ben moon", limit=20)
    assert rows
    assert all("ben moon" in (r["setter"] or "").lower() for r in rows)


def test_load_2016_has_thousands():
    rows = static_catalog.load_layout("2016")
    assert len(rows) > 10_000
    sample = rows[0]
    assert {"id", "name", "grade", "holds", "layout"} <= set(sample.keys())
    assert len(sample["id"]) == 16


def test_search_filters_by_grade():
    rows = static_catalog.search("2016", grade="8A", limit=100)
    assert all(r["grade"] == "8A" for r in rows)
    assert rows


def test_get_by_id_roundtrips():
    rows = static_catalog.search("2016", limit=1)
    target = rows[0]
    fetched = static_catalog.get("2016", target["id"])
    assert fetched == target


async def test_provider_search_climbs():
    p = MoonboardCatalogProvider()
    out = await p.search_climbs(None, ClimbQuery(layout_id="2016", limit=5))
    assert len(out) == 5
    assert out[0].provider == "moonboard_catalog"
    assert out[0].grade
    assert out[0].holds


async def test_provider_layouts():
    p = MoonboardCatalogProvider()
    layouts = await p.list_layouts(None)
    assert {l.id for l in layouts} >= {"2016", "2017"}


async def test_provider_no_auth_needed():
    p = MoonboardCatalogProvider()
    assert p.requires_credentials is False
    tok = await p.authenticate({})
    assert tok.value == "public"

from __future__ import annotations

import sqlite3

import httpx
import pytest

from kt.providers.base import (
    AuthToken,
    ClimbQuery,
    ProviderAuthError,
    ProviderStatus,
    ProviderUnavailable,
)
from kt.providers.kilter.client import KilterClient
from kt.providers.kilter.legacy_catalog import KilterLegacyCatalog
from kt.providers.kilter.legacy_provider import KilterLegacyProvider
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
    assert tok.extras["username"] == "u"
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


async def test_authenticate_schema_drift_is_unavailable():
    def handler(req): return httpx.Response(200, json=["unexpected"])
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


async def test_legacy_provider_lists_boards_and_searches_climbs(tmp_path):
    db_path = tmp_path / "kilter.sqlite3"
    _write_legacy_catalog(db_path)

    p = KilterLegacyProvider(
        legacy_catalog=KilterLegacyCatalog(db_path, provider_key="kilter_legacy")
    )

    layouts = await p.list_layouts(None)
    assert [layout.id for layout in layouts] == ["14"]
    assert layouts[0].angles == list(range(5, 75, 5))
    assert layouts[0].extras["kind"] == "board"
    assert layouts[0].extras["climb_count"] == 2

    climbs = await p.search_climbs(
        None,
        ClimbQuery(layout_id="14", angle=40, text="swoop", holds_required=("1080",)),
    )
    assert [climb.id for climb in climbs] == ["kilter:14:uuid-a"]
    assert [climb.provider for climb in climbs] == ["kilter_legacy"]
    assert climbs[0].grade == "V6"
    assert climbs[0].holds == ["1080", "1110"]
    assert climbs[0].extras["route_grade"] == "5.12d"
    assert climbs[0].extras["image_urls"] == ["/api/images/original.png"]

    detail = await p.get_climb(
        AuthToken("kilter_legacy", "tok", extras={"board_id": "14", "angle": 40}),
        "kilter:14:uuid-a",
    )
    assert detail.name == "Swooped"
    assert detail.provider == "kilter_legacy"
    assert detail.extras["highlighted_holds"] == [
        {"position": 1080, "role_id": 12},
        {"position": 1110, "role_id": 15},
    ]


async def test_legacy_provider_validates_board_and_angle(tmp_path):
    db_path = tmp_path / "kilter.sqlite3"
    _write_legacy_catalog(db_path)
    p = KilterLegacyProvider(
        legacy_catalog=KilterLegacyCatalog(db_path, provider_key="kilter_legacy")
    )

    with pytest.raises(ProviderAuthError):
        await p.search_climbs(None, ClimbQuery(angle=40))
    with pytest.raises(ProviderAuthError):
        await p.search_climbs(None, ClimbQuery(layout_id="14", angle=999))


def _write_legacy_catalog(path):
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE products (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              is_listed INTEGER NOT NULL
            );
            CREATE TABLE product_sizes (
              id INTEGER PRIMARY KEY,
              product_id INTEGER NOT NULL,
              name TEXT NOT NULL,
              edge_left INTEGER NOT NULL,
              edge_right INTEGER NOT NULL,
              edge_bottom INTEGER NOT NULL,
              edge_top INTEGER NOT NULL,
              is_listed INTEGER NOT NULL,
              position INTEGER NOT NULL
            );
            CREATE TABLE layouts (
              id INTEGER PRIMARY KEY,
              product_id INTEGER NOT NULL
            );
            CREATE TABLE product_sizes_layouts_sets (
              product_size_id INTEGER NOT NULL,
              layout_id INTEGER NOT NULL,
              image_filename TEXT NOT NULL
            );
            CREATE TABLE climbs (
              uuid TEXT PRIMARY KEY,
              setter_username TEXT,
              name TEXT,
              description TEXT,
              frames TEXT,
              created_at TEXT,
              layout_id INTEGER,
              edge_left INTEGER,
              edge_right INTEGER,
              edge_bottom INTEGER,
              edge_top INTEGER,
              is_listed INTEGER
            );
            CREATE TABLE climb_stats (
              climb_uuid TEXT,
              angle INTEGER,
              display_difficulty INTEGER,
              ascensionist_count INTEGER
            );
            CREATE TABLE difficulty_grades (
              difficulty INTEGER PRIMARY KEY,
              boulder_name TEXT,
              route_name TEXT
            );
            INSERT INTO products VALUES (1, 'Kilter Board Original', 1);
            INSERT INTO product_sizes VALUES (14, 1, '7 x 10', 0, 100, 0, 100, 1, 1);
            INSERT INTO layouts VALUES (1, 1);
            INSERT INTO product_sizes_layouts_sets VALUES (14, 1, 'boards/original.png');
            INSERT INTO difficulty_grades VALUES (6, 'V6', '5.12d');
            INSERT INTO difficulty_grades VALUES (4, 'V4', '5.11d');
            INSERT INTO climbs VALUES (
              'uuid-a',
              'jwebxl',
              'Swooped',
              'A challenging overhang',
              'p1080r12p1110r15',
              '2025-01-02',
              1,
              10,
              90,
              10,
              90,
              1
            );
            INSERT INTO climbs VALUES (
              'uuid-b',
              'setter',
              'Other',
              '',
              'p1200r12',
              '2025-01-01',
              1,
              10,
              90,
              10,
              90,
              1
            );
            INSERT INTO climb_stats VALUES ('uuid-a', 40, 6, 42);
            INSERT INTO climb_stats VALUES ('uuid-b', 40, 4, 1);
            """
        )

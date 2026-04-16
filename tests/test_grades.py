from __future__ import annotations

import pytest
from httpx import AsyncClient

from kt.grades import convert, parse_to_v, v_to_font


@pytest.mark.parametrize(
    "raw,expected_v",
    [
        ("V0", 0),
        ("V5", 5),
        ("V17", 17),
        ("6A", 3),
        ("7A+", 7),
        ("8A", 11),
        ("9a", 17),
        ("5.12b", 6),
        ("5.14a", 11),
        ("VB", 0),
        ("V5/6", 5),
    ],
)
def test_parse_to_v(raw, expected_v):
    assert parse_to_v(raw) == expected_v


def test_parse_to_v_rejects_junk():
    assert parse_to_v("nonsense") is None
    assert parse_to_v("") is None
    assert parse_to_v(None) is None


def test_v_to_font_roundtrip():
    for v in range(0, 18):
        font = v_to_font(v)
        assert font is not None
        assert parse_to_v(font) == v


def test_convert_cross_system():
    assert convert("6A", "font", "v") == "V3"
    assert convert("V5", "v", "font") == "6C"
    assert convert("5.12b", "yds", "v") == "V6"
    assert convert("V11", "v", "uiaa") == "X-"


def test_convert_bad_system_raises():
    with pytest.raises(ValueError):
        convert("V5", "v", "unknown")


async def test_grades_systems_endpoint(client: AsyncClient):
    r = await client.get("/api/v1/grades/systems")
    assert r.status_code == 200
    assert set(r.json()["systems"]) == {"font", "v", "yds", "uiaa"}


async def test_grades_convert_endpoint(client: AsyncClient):
    r = await client.get(
        "/api/v1/grades/convert",
        params={"value": "7A", "from": "font", "to": "v"},
    )
    assert r.status_code == 200
    assert r.json()["to"]["value"] == "V6"


async def test_grades_convert_unrecognized(client: AsyncClient):
    r = await client.get(
        "/api/v1/grades/convert",
        params={"value": "zzz", "from": "font", "to": "v"},
    )
    assert r.status_code == 400

"""Board-location directory: ingest a GeoJSON feed of physical training
boards into the `board_locations` table.

Feed format matches Stevie-Ray/hangtime-climbing-boards (an auto-updating
dataset). Each feature is a Point with board metadata in properties.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from kt.db import db


async def ingest_geojson(
    source: str | Path | None = None,
) -> int:
    """Load a GeoJSON FeatureCollection and upsert each feature as a board
    location. Returns the number of features upserted.

    If ``source`` is None, the bundled sample is used.
    """
    if source is None:
        raw = (
            resources.files("kt.boards.data")
            .joinpath("sample_locations.geojson")
            .read_text()
        )
    else:
        raw = await asyncio.to_thread(Path(source).read_text)
    data = json.loads(raw)
    features = data.get("features") or []
    now = datetime.now(UTC).isoformat()
    count = 0
    for feat in features:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or [None, None]
        if geom.get("type") != "Point" or len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        if lat is None or lon is None:
            continue
        fid = str(props.get("id") or "")
        if not fid:
            continue
        await db().execute(
            """INSERT INTO board_locations(id, provider_key, gym_name, country, city,
                    lat, lon, angle_min, angle_max, board_type, board_family, setup_year,
                    layout_type, holdset_version, is_adjustable, updated_at, raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                   provider_key=excluded.provider_key,
                   gym_name=excluded.gym_name,
                   country=excluded.country,
                   city=excluded.city,
                   lat=excluded.lat,
                   lon=excluded.lon,
                   angle_min=excluded.angle_min,
                   angle_max=excluded.angle_max,
                   board_type=excluded.board_type,
                   board_family=excluded.board_family,
                   setup_year=excluded.setup_year,
                   layout_type=excluded.layout_type,
                   holdset_version=excluded.holdset_version,
                   is_adjustable=excluded.is_adjustable,
                   updated_at=excluded.updated_at,
                   raw_json=excluded.raw_json""",
            (
                fid,
                str(props.get("board_type") or ""),
                str(props.get("gym_name") or ""),
                str(props.get("country") or ""),
                str(props.get("city") or ""),
                float(lat),
                float(lon),
                _maybe_int(props.get("angle_min")),
                _maybe_int(props.get("angle_max")),
                str(props.get("board_type") or ""),
                _board_family(props),
                _maybe_int(props.get("setup_year")),
                _maybe_text(props.get("layout_type")),
                _maybe_text(props.get("holdset_version")),
                _is_adjustable(props),
                now,
                json.dumps(props),
            ),
        )
        count += 1
    await db().commit()
    return count


def _maybe_int(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _maybe_text(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text if text else None


def _board_family(props: dict[str, Any]) -> str:
    explicit = _maybe_text(props.get("board_family"))
    if explicit:
        return explicit.lower()
    fallback = _maybe_text(props.get("board_type"))
    if fallback:
        return fallback.lower()
    return "unknown"


def _is_adjustable(props: dict[str, Any]) -> int | None:
    explicit = props.get("is_adjustable")
    if explicit is not None:
        if isinstance(explicit, bool):
            return 1 if explicit else 0
        text = str(explicit).strip().lower()
        if text in {"1", "true", "yes"}:
            return 1
        if text in {"0", "false", "no"}:
            return 0
    angle_min = _maybe_int(props.get("angle_min"))
    angle_max = _maybe_int(props.get("angle_max"))
    if angle_min is None or angle_max is None:
        return None
    return 1 if angle_min != angle_max else 0

from __future__ import annotations

import json
import math
from typing import Any

from kt.db import db


class BoardsRepo:
    async def get(self, bid: str) -> dict[str, Any] | None:
        async with db().execute(
            """SELECT id, provider_key, gym_name, country, city, lat, lon,
                      angle_min, angle_max, board_type, updated_at, raw_json
               FROM board_locations WHERE id=?""",
            (bid,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return _unpack(dict(row))

    async def list_all(
        self, board_type: str | None = None, country: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        sql = [
            """SELECT id, provider_key, gym_name, country, city, lat, lon,
                      angle_min, angle_max, board_type, updated_at, raw_json
               FROM board_locations WHERE 1=1"""
        ]
        args: list[Any] = []
        if board_type:
            sql.append("AND board_type=?")
            args.append(board_type)
        if country:
            sql.append("AND country=?")
            args.append(country.upper())
        sql.append("ORDER BY gym_name ASC LIMIT ?")
        args.append(limit)
        async with db().execute(" ".join(sql), args) as cur:
            rows = await cur.fetchall()
        return [_unpack(dict(r)) for r in rows]

    async def search_nearby(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        board_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        lat_min, lat_max, lon_min, lon_max, wraps = _bounding_box(lat, lon, radius_km)
        sql = [
            """SELECT id, provider_key, gym_name, country, city, lat, lon,
                      angle_min, angle_max, board_type, updated_at, raw_json
               FROM board_locations
               WHERE lat BETWEEN ? AND ?"""
        ]
        args: list[Any] = [lat_min, lat_max]

        if wraps:
            sql.append("AND (lon >= ? OR lon <= ?)")
            args.extend([lon_min, lon_max])
        else:
            sql.append("AND lon BETWEEN ? AND ?")
            args.extend([lon_min, lon_max])

        if board_type:
            sql.append("AND board_type=?")
            args.append(board_type)

        async with db().execute(" ".join(sql), args) as cur:
            rows = await cur.fetchall()

        out = []
        for r in rows:
            unpacked = _unpack(dict(r))
            d = _haversine_km(lat, lon, unpacked["lat"], unpacked["lon"])
            if d <= radius_km:
                unpacked["distance_km"] = round(d, 3)
                out.append(unpacked)
        out.sort(key=lambda x: x["distance_km"])
        return out[:limit]

    async def types(self) -> list[str]:
        async with db().execute(
            """SELECT DISTINCT board_type FROM board_locations
               WHERE board_type IS NOT NULL AND board_type != ''
               ORDER BY board_type ASC"""
        ) as cur:
            rows = await cur.fetchall()
        return [row["board_type"] for row in rows]

    async def count(self) -> int:
        async with db().execute("SELECT COUNT(*) FROM board_locations") as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0


def _unpack(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.pop("raw_json", None)
    row["properties"] = json.loads(raw) if raw else {}
    return row


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _bounding_box(
    lat: float, lon: float, radius_km: float
) -> tuple[float, float, float, float, bool]:
    lat_delta = radius_km / 110.574
    lat_min = max(-90.0, lat - lat_delta)
    lat_max = min(90.0, lat + lat_delta)

    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-6:
        lon_delta = 180.0
    else:
        lon_delta = min(180.0, radius_km / (111.320 * abs(cos_lat)))

    raw_lon_min = lon - lon_delta
    raw_lon_max = lon + lon_delta

    if raw_lon_min < -180.0:
        return lat_min, lat_max, raw_lon_min + 360.0, raw_lon_max, True
    if raw_lon_max > 180.0:
        return lat_min, lat_max, raw_lon_min, raw_lon_max - 360.0, True
    return lat_min, lat_max, raw_lon_min, raw_lon_max, False

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
        # Haversine filter in Python; at the scale of known boards this is fine.
        rows = await self.list_all(board_type=board_type, limit=10_000)
        out = []
        for r in rows:
            d = _haversine_km(lat, lon, r["lat"], r["lon"])
            if d <= radius_km:
                r["distance_km"] = round(d, 3)
                out.append(r)
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

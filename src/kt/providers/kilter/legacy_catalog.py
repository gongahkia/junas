from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from kt.providers.base import (
    Climb,
    ClimbQuery,
    Layout,
    ProviderAuthError,
    ProviderUnavailable,
    matches_holds,
)

SUPPORTED_ANGLES = tuple(range(5, 75, 5))
FRAME_HOLD_RE = re.compile(r"p(\d+)r(\d+)")


class KilterLegacyCatalog:
    """Read-only adapter for the legacy Aurora/Kilter SQLite catalog.

    The old full-stack app queried a local SQLite catalog extracted from the
    Kilter mobile bundle. This adapter keeps that backend contract available
    when a caller provides `KT_KILTER_LEGACY_DB_PATH`, without reviving the
    retired download/bootstrap flow.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else None

    @classmethod
    def from_env(cls) -> KilterLegacyCatalog:
        return cls(os.environ.get("KT_KILTER_LEGACY_DB_PATH"))

    @property
    def available(self) -> bool:
        return self.path is not None and self.path.exists()

    def list_layouts(self) -> list[Layout]:
        rows = self._fetch_all(
            """
            SELECT
              ps.id AS id,
              ps.name AS name,
              p.name AS kilter_name,
              COALESCE(MIN(NULLIF(psl.image_filename, '')), '') AS preview_image_filename,
              COUNT(DISTINCT c.uuid) AS climb_count
            FROM product_sizes AS ps
            JOIN products AS p
              ON ps.product_id = p.id
            LEFT JOIN product_sizes_layouts_sets AS psl
              ON psl.product_size_id = ps.id
            LEFT JOIN layouts AS l
              ON l.id = psl.layout_id AND l.product_id = ps.product_id
            LEFT JOIN climbs AS c
              ON c.layout_id = l.id
              AND c.is_listed = 1
              AND ps.edge_left <= c.edge_left
              AND ps.edge_right >= c.edge_right
              AND ps.edge_bottom <= c.edge_bottom
              AND ps.edge_top >= c.edge_top
            WHERE ps.is_listed = 1
              AND p.is_listed = 1
              AND p.name LIKE 'Kilter Board%'
            GROUP BY ps.id, ps.name, p.name
            ORDER BY p.name, ps.position, ps.id
            """,
        )
        return [
            Layout(
                id=str(row["id"]),
                name=f"{row['kilter_name']} {row['name']}".strip(),
                angles=list(SUPPORTED_ANGLES),
                extras={
                    "kind": "board",
                    "board_id": str(row["id"]),
                    "kilter_name": row["kilter_name"],
                    "climb_count": row["climb_count"],
                    "image_url": _image_url(row["preview_image_filename"]),
                },
            )
            for row in rows
        ]

    def search_climbs(self, query: ClimbQuery) -> list[Climb]:
        board_id = _parse_board_id(query.layout_id)
        angle = _parse_angle(query.angle)
        text_pattern = f"%{(query.text or '').strip()}%"
        rows = self._fetch_all(
            """
            SELECT
              c.uuid,
              c.setter_username AS setter_name,
              c.name AS climb_name,
              c.description,
              c.frames,
              c.created_at,
              ps.id AS product_size_id,
              GROUP_CONCAT(DISTINCT psl.image_filename) AS image_filenames,
              COALESCE(cs.ascensionist_count, 0) AS ascends,
              dg.boulder_name,
              dg.route_name
            FROM climbs c
            JOIN layouts l ON c.layout_id = l.id
            JOIN product_sizes ps ON (
              ps.product_id = l.product_id
              AND ps.edge_left <= c.edge_left
              AND ps.edge_right >= c.edge_right
              AND ps.edge_bottom <= c.edge_bottom
              AND ps.edge_top >= c.edge_top
            )
            JOIN product_sizes_layouts_sets psl
              ON psl.product_size_id = ps.id AND psl.layout_id = l.id
            JOIN climb_stats cs ON c.uuid = cs.climb_uuid AND cs.angle = ?
            JOIN difficulty_grades dg ON CAST(cs.display_difficulty AS INTEGER) = dg.difficulty
            WHERE c.is_listed = 1
              AND ps.id = ?
              AND (
                c.name LIKE ?
                OR c.setter_username LIKE ?
                OR dg.boulder_name LIKE ?
                OR dg.route_name LIKE ?
              )
            GROUP BY c.uuid, ps.id, cs.ascensionist_count, dg.boulder_name, dg.route_name
            ORDER BY ascends DESC, c.created_at DESC, c.uuid DESC, ps.id
            LIMIT ? OFFSET ?
            """,
            (
                angle,
                board_id,
                text_pattern,
                text_pattern,
                text_pattern,
                text_pattern,
                query.limit * 10 if (query.holds_required or query.holds_forbidden) else query.limit,
                query.offset,
            ),
        )
        climbs = [_to_climb(row, angle) for row in rows]
        if query.holds_required or query.holds_forbidden:
            climbs = [
                climb
                for climb in climbs
                if matches_holds(climb.holds, query.holds_required, query.holds_forbidden)
            ]
        return climbs[: query.limit]

    def get_climb(self, climb_id: str, query: ClimbQuery) -> Climb:
        requested_board_id, uuid = _parse_climb_id(climb_id)
        board_id = _parse_board_id(query.layout_id or str(requested_board_id))
        if requested_board_id != board_id:
            raise ProviderAuthError(f"climb {climb_id} does not belong to board {board_id}")
        angle = _parse_angle(query.angle)
        rows = self._fetch_all(
            """
            SELECT
              c.uuid,
              c.setter_username AS setter_name,
              c.name AS climb_name,
              c.description,
              c.frames,
              c.created_at,
              ps.id AS product_size_id,
              GROUP_CONCAT(DISTINCT psl.image_filename) AS image_filenames,
              COALESCE(cs.ascensionist_count, 0) AS ascends,
              dg.boulder_name,
              dg.route_name
            FROM climbs c
            JOIN layouts l ON c.layout_id = l.id
            JOIN product_sizes ps ON (
              ps.product_id = l.product_id
              AND ps.edge_left <= c.edge_left
              AND ps.edge_right >= c.edge_right
              AND ps.edge_bottom <= c.edge_bottom
              AND ps.edge_top >= c.edge_top
            )
            JOIN product_sizes_layouts_sets psl
              ON psl.product_size_id = ps.id AND psl.layout_id = l.id
            JOIN climb_stats cs ON c.uuid = cs.climb_uuid AND cs.angle = ?
            JOIN difficulty_grades dg ON CAST(cs.display_difficulty AS INTEGER) = dg.difficulty
            WHERE c.is_listed = 1
              AND c.uuid = ?
              AND ps.id = ?
            GROUP BY c.uuid, ps.id, cs.ascensionist_count, dg.boulder_name, dg.route_name
            LIMIT 1
            """,
            (angle, uuid, board_id),
        )
        if not rows:
            raise KeyError(climb_id)
        return _to_climb(rows[0], angle)

    def _fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if not self.available:
            raise ProviderUnavailable(
                "kilter legacy catalog not configured; set KT_KILTER_LEGACY_DB_PATH "
                "to an extracted Kilter SQLite catalog"
            )
        try:
            with sqlite3.connect(str(self.path)) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(row) for row in conn.execute(sql, params).fetchall()]
        except sqlite3.Error as e:
            raise ProviderUnavailable(f"kilter legacy catalog query failed: {e}") from e


def _parse_board_id(raw: str | None) -> int:
    if not raw:
        raise ProviderAuthError("kilter board id is required as layout_id")
    try:
        board_id = int(raw)
    except ValueError as e:
        raise ProviderAuthError(f"invalid kilter board id: {raw}") from e
    if board_id <= 0:
        raise ProviderAuthError(f"invalid kilter board id: {raw}")
    return board_id


def _parse_angle(raw: int | None) -> int:
    if raw is None:
        raise ProviderAuthError("kilter angle is required")
    if raw not in SUPPORTED_ANGLES:
        raise ProviderAuthError(f"unsupported kilter angle: {raw}")
    return raw


def _parse_climb_id(climb_id: str) -> tuple[int, str]:
    match = re.fullmatch(r"kilter:(\d+):(.+)", climb_id)
    if not match:
        raise ProviderAuthError(f"invalid kilter climb id: {climb_id}")
    return int(match.group(1)), match.group(2)


def _to_climb(row: dict[str, Any], angle: int) -> Climb:
    board_id = int(row["product_size_id"])
    uuid = str(row["uuid"])
    image_urls = [_image_url(filename) for filename in _split_images(row.get("image_filenames"))]
    image_urls = [url for url in image_urls if url]
    return Climb(
        id=f"kilter:{board_id}:{uuid}",
        provider="kilter",
        name=str(row.get("climb_name") or ""),
        setter=row.get("setter_name"),
        grade=row.get("boulder_name"),
        angle=angle,
        ascents=row.get("ascends"),
        holds=_frame_hold_tokens(row.get("frames")),
        extras={
            "external_id": uuid,
            "description": row.get("description"),
            "board_id": str(board_id),
            "route_grade": row.get("route_name"),
            "frames": row.get("frames"),
            "created_at": row.get("created_at"),
            "image_urls": image_urls,
            "highlighted_holds": _highlighted_holds(row.get("frames")),
        },
    )


def _split_images(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            return [str(item) for item in json.loads(text) if item]
        except (TypeError, ValueError):
            return []
    return [item for item in text.split(",") if item]


def _image_url(filename: Any) -> str | None:
    if not filename:
        return None
    return "/api/images/" + Path(str(filename)).name


def _frame_hold_tokens(frames: Any) -> list[str]:
    return [match.group(1) for match in FRAME_HOLD_RE.finditer(str(frames or ""))]


def _highlighted_holds(frames: Any) -> list[dict[str, int]]:
    return [
        {"position": int(match.group(1)), "role_id": int(match.group(2))}
        for match in FRAME_HOLD_RE.finditer(str(frames or ""))
    ]

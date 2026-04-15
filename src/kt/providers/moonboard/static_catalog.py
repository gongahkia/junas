"""Bundled MoonBoard problem catalog (2016 + 2017 layouts).

Source: lucien1011/MoonBoard-Route (MIT). The dataset records have shape
{Grade, Moves, UserRating}; we synthesize a stable id by hashing moves+grade
since the upstream JSON does not carry one."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from importlib import resources
from typing import Any

_LAYOUT_FILES: dict[str, str] = {
    "2016": "2016.json",
    "2017": "2017.json",
}


def supported_layouts() -> list[str]:
    return list(_LAYOUT_FILES.keys())


def _stable_id(grade: str, moves: list[str]) -> str:
    h = hashlib.sha1()
    h.update(grade.encode("utf-8"))
    for m in moves:
        h.update(b"|")
        h.update(m.encode("utf-8"))
    return h.hexdigest()[:16]


@lru_cache(maxsize=8)
def load_layout(layout: str) -> list[dict[str, Any]]:
    fn = _LAYOUT_FILES.get(layout)
    if fn is None:
        return []
    raw = resources.files("kt.providers.moonboard.data").joinpath(fn).read_text()
    data = json.loads(raw)
    out: list[dict[str, Any]] = []
    for rec in data:
        moves = list(rec.get("Moves") or [])
        grade = str(rec.get("Grade") or "")
        out.append(
            {
                "id": _stable_id(grade, moves),
                "name": f"{grade} ({len(moves)} holds)",
                "grade": grade,
                "user_rating": rec.get("UserRating", 0),
                "holds": moves,
                "layout": layout,
            }
        )
    return out


def search(
    layout: str,
    text: str | None = None,
    grade: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rows = load_layout(layout)
    if grade:
        rows = [r for r in rows if r["grade"] == grade]
    if text:
        t = text.lower()
        rows = [
            r
            for r in rows
            if t in r["name"].lower() or t in r["grade"].lower() or t in r["id"]
        ]
    return rows[offset : offset + limit]


def get(layout: str, problem_id: str) -> dict[str, Any] | None:
    for r in load_layout(layout):
        if r["id"] == problem_id:
            return r
    return None

"""Bundled MoonBoard problem catalogs.

Two complementary sources, both vendored under data/:

* `benchmarks.json` — community benchmark problems from
  https://moonboard.simonchase.com/benchmarks.json. Rich metadata: real
  MoonBoard ids, names, setter, repeats, hold roles (start/mid/end), star
  ratings, sandbag score. ~2k problems across all board generations.

* `2016.json` / `2017.json` — full layout catalogs from
  lucien1011/MoonBoard-Route (MIT). Schema {Grade, Moves, UserRating}; no
  names/setters but covers ~32k problems.

The catalog is unified so consumers see a single search surface.
"""

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
_BENCHMARKS_FILE = "benchmarks.json"


def supported_layouts() -> list[str]:
    return ["benchmarks", *_LAYOUT_FILES.keys()]


def _read(filename: str) -> str:
    return resources.files("kt.providers.moonboard.data").joinpath(filename).read_text()


def _stable_id(grade: str, moves: list[str]) -> str:
    h = hashlib.sha1(usedforsecurity=False)
    h.update(grade.encode("utf-8"))
    for m in moves:
        h.update(b"|")
        h.update(m.encode("utf-8"))
    return h.hexdigest()[:16]


@lru_cache(maxsize=8)
def load_layout(layout: str) -> list[dict[str, Any]]:
    if layout == "benchmarks":
        return _load_benchmarks()
    fn = _LAYOUT_FILES.get(layout)
    if fn is None:
        return []
    raw = json.loads(_read(fn))
    out: list[dict[str, Any]] = []
    for rec in raw:
        moves = list(rec.get("Moves") or [])
        grade = str(rec.get("Grade") or "")
        out.append(
            {
                "id": _stable_id(grade, moves),
                "name": f"{grade} ({len(moves)} holds)",
                "grade": grade,
                "setter": None,
                "user_rating": rec.get("UserRating", 0),
                "repeats": None,
                "holds": moves,
                "start_holds": [],
                "mid_holds": [],
                "end_holds": [],
                "layout": layout,
                "mb_type": None,
            }
        )
    return out


def _load_benchmarks() -> list[dict[str, Any]]:
    raw = json.loads(_read(_BENCHMARKS_FILE))
    out: list[dict[str, Any]] = []
    for rec in raw:
        start = list(rec.get("start_holds") or [])
        mid = list(rec.get("mid_holds") or [])
        end = list(rec.get("end_holds") or [])
        out.append(
            {
                "id": str(rec.get("id")),
                "name": str(rec.get("name") or ""),
                "grade": _font_grade(rec.get("grade")),
                "setter": rec.get("setter"),
                "user_rating": rec.get("avg_user_stars"),
                "repeats": rec.get("repeats"),
                "holds": [*start, *mid, *end],
                "start_holds": start,
                "mid_holds": mid,
                "end_holds": end,
                "layout": "benchmarks",
                "mb_type": rec.get("mb_type"),
            }
        )
    return out


# simonchase encodes grades as integers; map to Font scale matching MoonBoard.
_FONT_GRADES = ["6A", "6A+", "6B", "6B+", "6C", "6C+", "7A", "7A+", "7B", "7B+",
                "7C", "7C+", "8A", "8A+", "8B", "8B+", "8C", "8C+"]


def _font_grade(value: Any) -> str:
    if isinstance(value, int) and 0 <= value < len(_FONT_GRADES):
        return _FONT_GRADES[value]
    return str(value) if value is not None else ""


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
            if t in r["name"].lower()
            or t in (r["setter"] or "").lower()
            or t in r["grade"].lower()
        ]
    return rows[offset : offset + limit]


def get(layout: str, problem_id: str) -> dict[str, Any] | None:
    for r in load_layout(layout):
        if r["id"] == problem_id:
            return r
    return None

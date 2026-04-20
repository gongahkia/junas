"""Bundled MoonBoard problem catalogs.

Two complementary sources, both vendored under data/:

* `benchmarks.json` — community benchmark problems from
  https://moonboard.simonchase.com/benchmarks.json. Rich metadata: real
  MoonBoard ids, names, setter, repeats, hold roles (start/mid/end), star
  ratings, sandbag score. ~2k problems across all board generations.

* `2016.json` / `2017.json` — full layout catalogs from
  lucien1011/MoonBoard-Route (MIT). Schema {Grade, Moves, UserRating}; no
  names/setters but covers ~32k problems.

The catalog is unified so consumers see a single search surface, while also
exposing setup-specific benchmark views (2016/2017/2019/2024/mini variants)
derived from `mb_type` in the bundled benchmark data.
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
_MB_TYPE_LAYOUTS: dict[int, str] = {
    # Community-inferred mapping from benchmark `mb_type` codes to setup families.
    0: "2016_benchmarks",
    1: "2017_benchmarks",
    2: "2019_benchmarks",
    3: "mini_2020_benchmarks",
    4: "2024_benchmarks",
    5: "mini_2025_benchmarks",
}
_MB_TYPE_LAYOUTS_REVERSE: dict[str, int] = {v: k for k, v in _MB_TYPE_LAYOUTS.items()}

_LAYOUT_LABELS: dict[str, str] = {
    "benchmarks": "MoonBoard Benchmarks (all setups)",
    "2016": "MoonBoard 2016 (full static)",
    "2017": "MoonBoard 2017 (full static)",
    "2016_benchmarks": "MoonBoard 2016 Benchmarks",
    "2017_benchmarks": "MoonBoard 2017 Benchmarks",
    "2019_benchmarks": "MoonBoard 2019 Benchmarks",
    "mini_2020_benchmarks": "Mini MoonBoard 2020 Benchmarks",
    "2024_benchmarks": "MoonBoard 2024 Benchmarks",
    "mini_2025_benchmarks": "Mini MoonBoard 2025 Benchmarks",
}


def supported_layouts() -> list[str]:
    return ["benchmarks", *_LAYOUT_FILES.keys(), *_MB_TYPE_LAYOUTS.values()]


def layout_name(layout: str) -> str:
    return _LAYOUT_LABELS.get(layout, f"MoonBoard {layout}")


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
    mb_type = _MB_TYPE_LAYOUTS_REVERSE.get(layout)
    if mb_type is not None:
        return _load_benchmarks(filter_mb_type=mb_type, layout_id=layout)
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


def _load_benchmarks(
    *,
    filter_mb_type: int | None = None,
    layout_id: str = "benchmarks",
) -> list[dict[str, Any]]:
    raw = json.loads(_read(_BENCHMARKS_FILE))
    out: list[dict[str, Any]] = []
    for rec in raw:
        mb_type = _safe_int(rec.get("mb_type"))
        if filter_mb_type is not None and mb_type != filter_mb_type:
            continue
        start = list(rec.get("start_holds") or [])
        mid = list(rec.get("mid_holds") or [])
        end = list(rec.get("end_holds") or [])
        mapped_layout = _MB_TYPE_LAYOUTS.get(mb_type or -1)
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
                "layout": layout_id,
                "mb_type": rec.get("mb_type"),
                "setup": mapped_layout,
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


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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

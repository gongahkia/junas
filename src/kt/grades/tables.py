"""Static bouldering-grade conversion tables, keyed by canonical V-scale int.

Indicative mappings — see theCrag's grade article for discussion of why no
single table is universally accepted. We pick common defaults and expose
round-trip helpers. Sub-grade precision (e.g. 6B vs 6B+) is preserved on
output but collapsed on parse (we map both to V4) — acceptable for filter
and display, lossy for exact round-trip.
"""

from __future__ import annotations

import re
from typing import Final

SYSTEMS: Final[tuple[str, ...]] = ("font", "v", "yds", "uiaa")

V_TO_FONT: Final[dict[int, str]] = {
    0: "4",
    1: "5",
    2: "5+",
    3: "6A",
    4: "6B",
    5: "6C",
    6: "7A",
    7: "7A+",
    8: "7B",
    9: "7C",
    10: "7C+",
    11: "8A",
    12: "8A+",
    13: "8B",
    14: "8B+",
    15: "8C",
    16: "8C+",
    17: "9A",
}

V_TO_YDS: Final[dict[int, str]] = {
    0: "5.10a",
    1: "5.10b",
    2: "5.10c",
    3: "5.11a",
    4: "5.11b",
    5: "5.11d",
    6: "5.12b",
    7: "5.12c",
    8: "5.12d",
    9: "5.13b",
    10: "5.13c",
    11: "5.14a",
    12: "5.14b",
    13: "5.14c",
    14: "5.14d",
    15: "5.15a",
    16: "5.15b",
    17: "5.15c",
}

V_TO_UIAA: Final[dict[int, str]] = {
    0: "VI",
    1: "VI+",
    2: "VII-",
    3: "VII",
    4: "VII+",
    5: "VIII-",
    6: "VIII",
    7: "VIII+",
    8: "IX-",
    9: "IX",
    10: "IX+",
    11: "X-",
    12: "X",
    13: "X+",
    14: "XI-",
    15: "XI",
    16: "XI+",
    17: "XII-",
}


def v_to_font(v: int) -> str | None:
    return V_TO_FONT.get(v)


def v_to_yds(v: int) -> str | None:
    return V_TO_YDS.get(v)


def v_to_uiaa(v: int) -> str | None:
    return V_TO_UIAA.get(v)


_FONT_TO_V: Final[dict[str, int]] = {
    v.upper(): k for k, v in V_TO_FONT.items()
} | {
    # Lowercase sub-grades and common variants (6a == 6A, 6A- ~ 6A).
    "6A-": 3,
    "6B-": 4,
    "6C-": 5,
    "6A/6B": 3,
    "6B/6C": 4,
    "6C/7A": 5,
}

_YDS_TO_V: Final[dict[str, int]] = {
    v.upper(): k for k, v in V_TO_YDS.items()
}


_V_RE = re.compile(r"^V(?:B|\d{1,2})(?:[+/-]V?\d{1,2})?$", re.IGNORECASE)
_FONT_RE = re.compile(r"^([4-9])([ABCabc])([+-])?$")
_FONT_SIMPLE_RE = re.compile(r"^[4-5](?:\+)?$")
_YDS_RE = re.compile(r"^5\.([0-9]{1,2})([a-dA-D])?([+/-]?)$")


def parse_to_v(raw: str | None) -> int | None:
    """Best-effort parse of any grading-system string into canonical V int."""
    if raw is None:
        return None
    s = str(raw).strip().upper()
    if not s:
        return None

    # Strip common annotations
    s = s.replace(" ", "")

    # V-scale
    if _V_RE.match(s):
        if s.startswith("VB"):
            return 0
        # Take the lower bound when the grade is a range like V5-6
        m = re.match(r"^V(\d{1,2})", s)
        if m:
            try:
                v = int(m.group(1))
            except ValueError:
                return None
            if 0 <= v <= 17:
                return v
        return None

    # Font (e.g. 6A, 6A+, 7C+, 8A)
    if s in _FONT_TO_V:
        return _FONT_TO_V[s]
    m = _FONT_RE.match(s)
    if m:
        tier = m.group(1)
        letter = m.group(2)
        plus = m.group(3) == "+"
        key = f"{tier}{letter}{'+' if plus else ''}"
        if key in _FONT_TO_V:
            return _FONT_TO_V[key]
        # Fall back to the nearest grade without the plus
        return _FONT_TO_V.get(f"{tier}{letter}")
    if _FONT_SIMPLE_RE.match(s):
        return _FONT_TO_V.get(s)

    # YDS (e.g. 5.11b, 5.12a/b)
    if s in _YDS_TO_V:
        return _YDS_TO_V[s]
    m = _YDS_RE.match(s)
    if m:
        tier = m.group(1)
        letter = (m.group(2) or "").lower()
        # Normalize to the closest canonical string; trim plus/slash.
        key = f"5.{int(tier)}{letter}"
        return _YDS_TO_V.get(key.upper())

    return None


def system_value(v: int, system: str) -> str | None:
    system = system.lower()
    if system == "v":
        return f"V{v}"
    if system == "font":
        return v_to_font(v)
    if system == "yds":
        return v_to_yds(v)
    if system == "uiaa":
        return v_to_uiaa(v)
    return None


def convert(value: str, from_system: str, to_system: str) -> str | None:
    from_system = from_system.lower()
    to_system = to_system.lower()
    if from_system not in SYSTEMS or to_system not in SYSTEMS:
        raise ValueError(f"system must be one of {SYSTEMS}")
    if from_system == "v":
        m = re.match(r"^V?(\d{1,2})", value.strip().upper())
        v = int(m.group(1)) if m else None
    else:
        v = parse_to_v(value)
    if v is None or not (0 <= v <= 17):
        return None
    return system_value(v, to_system)

"""Citation perturbation engine for SGLB-11.

Seven mechanical perturbation classes that produce fabricated citations
from real ones (or from grammar templates). Each perturbation function
is deterministic given a seed, so the dataset is reproducible.

The verifier in ``benchmark.dataset_builders.sglb_11`` asserts that no
perturbation accidentally produces a citation that exists in the real
pool.

Each perturbation function:
- Takes a parsed citation (or just a string for wholesale_fabrication)
  and a ``random.Random`` instance.
- Returns the perturbed citation string + a ``perturbation_type`` tag.

Perturbation taxonomy (from SGLB-11 spec, ``docs/sglb_specs/SGLB-11.md``):

| Type | Description |
|---|---|
| year_off | Year shifted by ±[1..5] |
| volume_off | Volume number changed for SLR / SLR(R) |
| page_off | Page number changed for SLR / SLR(R), or case number for neutral |
| case_name_swap | Real case name → invented case name |
| court_swap | Court code substituted (SGCA ↔ SGHC etc.) |
| wholesale_fabrication | Plausible grammar-conformant citation built from scratch |
| composite | Two or more perturbations applied together |

Pre-computed surname pools and court codes live at module level so the
generator is reproducible across runs.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Literal

PerturbationType = Literal[
    "year_off",
    "volume_off",
    "page_off",
    "case_name_swap",
    "court_swap",
    "wholesale_fabrication",
    "composite",
]


# Hand-curated pools used by case_name_swap and wholesale_fabrication.
# These are common surnames + entity-stem tokens that compose into
# plausible-looking SG case names. Sourced from generic surname lists,
# not from real case parties — keeps the synthesis defensible.
_SURNAMES: tuple[str, ...] = (
    "Tan", "Lim", "Lee", "Wong", "Chua", "Ong", "Goh", "Ng", "Teo", "Chia",
    "Koh", "Yeo", "Chong", "Cheong", "Soh", "Khoo", "Quek", "Phua", "Sim",
    "Loh", "Yap", "Lau", "Chen", "Wu", "Zhang", "Liu", "Huang", "Zhao",
    "Suresh", "Kumar", "Singh", "Iyer", "Mohamed", "Rahman", "Ibrahim",
    "Ali", "Hassan", "Aziz", "Pillai", "Pereira",
)

_COMPANY_STEMS: tuple[str, ...] = (
    "Pte Ltd", "Holdings Pte Ltd", "International Pte Ltd",
    "Trading Pte Ltd", "Investments Pte Ltd", "Corporation",
    "Marine Pte Ltd", "Engineering Pte Ltd", "Services Pte Ltd",
    "Logistics Pte Ltd",
)

_COMPANY_PREFIXES: tuple[str, ...] = (
    "Acme", "Globex", "Tan & Sons", "Lim Brothers", "Stellar",
    "Pioneer", "Sentinel", "Apex", "Meridian", "Citadel",
)

# Canonical SG court codes used for neutral citations + swaps.
SG_COURT_CODES: tuple[str, ...] = (
    "SGCA", "SGHC", "SGHCR", "SGDC", "SGMC", "SGFC", "SGIA", "SGHCF",
)


@dataclass(frozen=True)
class Citation:
    """A parsed citation with the bits each perturbation may need."""

    raw: str
    kind: Literal["neutral_case", "slr_r_case", "slr_case"]
    year: int
    court: str = ""  # neutral only
    case_no: int = 0  # neutral only
    volume: int = 0  # SLR / SLR(R) only
    page: int = 0  # SLR / SLR(R) only
    case_name: str = ""  # optional party name prefix, e.g. "Tan Kim Seng v Adam Ibrahim"


_NEUTRAL_RE = re.compile(r"^(?:(?P<name>.+?)\s+)?\[(?P<year>\d{4})\]\s+(?P<court>SG[A-Z]+)\s+(?P<num>\d+)$")
_SLR_R_RE = re.compile(r"^(?:(?P<name>.+?)\s+)?\[(?P<year>\d{4})\]\s+(?P<vol>\d+)\s+SLR\(R\)\s+(?P<page>\d+)$")
_SLR_RE = re.compile(r"^(?:(?P<name>.+?)\s+)?\[(?P<year>\d{4})\]\s+(?P<vol>\d+)\s+SLR\s+(?P<page>\d+)$")


def parse_citation(s: str) -> Citation | None:
    """Parse a citation string into a ``Citation``.

    Returns None if the string doesn't match a known SG case grammar.
    Pinpoints / supra / Ibid / statute citations are out of scope — this
    is the perturbation surface for case citations only.
    """
    s = s.strip().rstrip(".")
    if m := _NEUTRAL_RE.match(s):
        return Citation(
            raw=s,
            kind="neutral_case",
            year=int(m.group("year")),
            court=m.group("court"),
            case_no=int(m.group("num")),
            case_name=(m.group("name") or "").strip(),
        )
    if m := _SLR_R_RE.match(s):
        return Citation(
            raw=s,
            kind="slr_r_case",
            year=int(m.group("year")),
            volume=int(m.group("vol")),
            page=int(m.group("page")),
            case_name=(m.group("name") or "").strip(),
        )
    if m := _SLR_RE.match(s):
        return Citation(
            raw=s,
            kind="slr_case",
            year=int(m.group("year")),
            volume=int(m.group("vol")),
            page=int(m.group("page")),
            case_name=(m.group("name") or "").strip(),
        )
    return None


def _format(citation: Citation) -> str:
    if citation.kind == "neutral_case":
        body = f"[{citation.year}] {citation.court} {citation.case_no}"
    elif citation.kind == "slr_r_case":
        body = f"[{citation.year}] {citation.volume} SLR(R) {citation.page}"
    else:
        body = f"[{citation.year}] {citation.volume} SLR {citation.page}"
    return f"{citation.case_name} {body}" if citation.case_name else body


def _invent_case_name(rng: random.Random) -> str:
    """Build a plausible 'X v Y' or 'X v Y Pte Ltd' party-name string."""
    plaintiff = rng.choice(_SURNAMES) + " " + rng.choice(_SURNAMES)
    if rng.random() < 0.4:
        defendant = rng.choice(_COMPANY_PREFIXES) + " " + rng.choice(_COMPANY_STEMS)
    else:
        defendant = rng.choice(_SURNAMES) + " " + rng.choice(_SURNAMES)
    return f"{plaintiff} v {defendant}"


# === Perturbation functions ===


def year_off(citation: Citation, rng: random.Random) -> str:
    """Shift the year by ±[1..5], not zero."""
    delta = rng.choice([-5, -4, -3, -2, -1, 1, 2, 3, 4, 5])
    new = Citation(**{**citation.__dict__, "year": citation.year + delta})
    return _format(new)


def volume_off(citation: Citation, rng: random.Random) -> str:
    """Change the volume number for SLR / SLR(R). Raises on neutral."""
    if citation.kind == "neutral_case":
        raise ValueError("volume_off does not apply to neutral citations")
    delta = rng.choice([-3, -2, -1, 1, 2, 3])
    new_vol = max(1, citation.volume + delta)
    if new_vol == citation.volume:
        new_vol += 1
    new = Citation(**{**citation.__dict__, "volume": new_vol})
    return _format(new)


def page_off(citation: Citation, rng: random.Random) -> str:
    """Shift the page (SLR / SLR(R)) or the case number (neutral) by a
    meaningful amount."""
    delta = rng.choice([-100, -50, -10, 10, 50, 100])
    if citation.kind == "neutral_case":
        new_n = max(1, citation.case_no + delta)
        if new_n == citation.case_no:
            new_n += 1
        new = Citation(**{**citation.__dict__, "case_no": new_n})
    else:
        new_p = max(1, citation.page + delta)
        if new_p == citation.page:
            new_p += 1
        new = Citation(**{**citation.__dict__, "page": new_p})
    return _format(new)


def case_name_swap(citation: Citation, rng: random.Random) -> str:
    """Replace the case name with an invented one. The citation
    body (year + court/volume + number) is preserved."""
    invented = _invent_case_name(rng)
    new = Citation(**{**citation.__dict__, "case_name": invented})
    return _format(new)


def court_swap(citation: Citation, rng: random.Random) -> str:
    """Substitute the court code for a different SG court. Raises on
    SLR / SLR(R) (no court field)."""
    if citation.kind != "neutral_case":
        raise ValueError("court_swap only applies to neutral citations")
    candidates = [c for c in SG_COURT_CODES if c != citation.court]
    new_court = rng.choice(candidates)
    new = Citation(**{**citation.__dict__, "court": new_court})
    return _format(new)


def wholesale_fabrication(rng: random.Random) -> str:
    """Build a plausible neutral citation from scratch. Year is bounded
    to a plausible SG legal-era range; court + case_no are random."""
    year = rng.randint(1990, 2025)
    court = rng.choice(SG_COURT_CODES)
    case_no = rng.randint(1, 400)
    name = _invent_case_name(rng) if rng.random() < 0.5 else ""
    citation = Citation(
        raw="",
        kind="neutral_case",
        year=year,
        court=court,
        case_no=case_no,
        case_name=name,
    )
    return _format(citation)


def composite(citation: Citation, rng: random.Random) -> str:
    """Apply two perturbations in sequence (year_off then court/volume).

    Picks the second perturbation based on the citation kind so the
    composition is valid.
    """
    step1 = year_off(citation, rng)
    parsed = parse_citation(step1)
    assert parsed is not None, f"year_off produced unparseable: {step1!r}"
    if parsed.kind == "neutral_case":
        return court_swap(parsed, rng)
    return volume_off(parsed, rng)


PERTURBATION_TYPES: tuple[PerturbationType, ...] = (
    "year_off",
    "volume_off",
    "page_off",
    "case_name_swap",
    "court_swap",
    "wholesale_fabrication",
    "composite",
)


def applicable_perturbations(citation: Citation) -> list[PerturbationType]:
    """Which perturbation classes legitimately apply to a given citation."""
    base = ["year_off", "page_off", "case_name_swap", "wholesale_fabrication", "composite"]
    if citation.kind == "neutral_case":
        base.append("court_swap")
    else:
        base.append("volume_off")
    return base  # type: ignore[return-value]


def apply(perturbation: PerturbationType, citation: Citation | None, rng: random.Random) -> str:
    """Dispatch to the right perturbation function."""
    if perturbation == "wholesale_fabrication":
        return wholesale_fabrication(rng)
    if citation is None:
        raise ValueError(f"{perturbation!r} requires a source citation")
    if perturbation == "year_off":
        return year_off(citation, rng)
    if perturbation == "volume_off":
        return volume_off(citation, rng)
    if perturbation == "page_off":
        return page_off(citation, rng)
    if perturbation == "case_name_swap":
        return case_name_swap(citation, rng)
    if perturbation == "court_swap":
        return court_swap(citation, rng)
    if perturbation == "composite":
        return composite(citation, rng)
    raise ValueError(f"unknown perturbation: {perturbation!r}")

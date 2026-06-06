"""Citation and statute normalisers used by SG-LegalBench scorers."""
from __future__ import annotations

import re

_STATUTE_LONG_NAMES: dict[str, str] = {
    "PDPA": "personal data protection act 2012",
    "EmA": "employment act 1968",
    "PC": "penal code 1871",
    "ROC2021": "rules of court 2021",
}

_STATUTE_ALIASES: dict[str, str] = {
    "pdpa": "PDPA",
    "pdpa2012": "PDPA",
    "personaldataprotectionact": "PDPA",
    "personaldataprotectionact2012": "PDPA",
    "ema": "EmA",
    "ema1968": "EmA",
    "employmentact": "EmA",
    "employmentact1968": "EmA",
    "pc": "PC",
    "pc1871": "PC",
    "penalcode": "PC",
    "penalcode1871": "PC",
    "roc2021": "ROC2021",
    "rulesofcourt": "ROC2021",
    "rulesofcourt2021": "ROC2021",
}

_DEFAULT_SECTION_STATUTE = _STATUTE_LONG_NAMES["PDPA"]
_SECTION_CITATION_RE = re.compile(
    r"^s\s+(?P<section>\d+[a-z]?(?:\([0-9a-z]+\))*)(?:\s+of\s+(?:the\s+)?(?P<statute>.+))?$",
    re.IGNORECASE,
)


def normalise_statute_name(value: str) -> str:
    """Return the canonical long-form statute name, or ``""`` if unknown."""
    text = re.sub(r"\s+", " ", (value or "").strip(" ."))
    if not text:
        return ""
    text = re.sub(r"^the\s+", "", text, flags=re.IGNORECASE)
    key = re.sub(r"[^a-z0-9]+", "", text.lower())
    short_name = _STATUTE_ALIASES.get(key)
    if not short_name:
        return ""
    return _STATUTE_LONG_NAMES[short_name]


def normalise_section_citation(value: str) -> str:
    """Normalise a section citation to a canonical comparison string.

    Tolerates common surface variations:
    - ``s 13``, ``s.13``, ``section 13``, ``Sec. 13`` to ``s 13``
    - statute aliases such as ``PDPA`` to their long-form Act name
    - ``Act 2012`` vs ``Act, 2012`` and trailing footnote punctuation
    """
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\b(?:section|sec)\.?\s+", "s ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bs\.\s*(?=\d)", "s ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bs\s+(?=\d)", "s ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bAct,\s+", "Act ", text)
    text = re.sub(r"\s+", " ", text).strip(" .").lower()
    match = _SECTION_CITATION_RE.match(text)
    if not match:
        return ""
    raw_statute = match.group("statute") or ""
    statute = normalise_statute_name(raw_statute)
    if raw_statute and not statute:
        return ""
    statute = statute or _DEFAULT_SECTION_STATUTE
    return f"s {match.group('section').lower()} of the {statute}"


__all__ = [
    "normalise_section_citation",
    "normalise_statute_name",
]

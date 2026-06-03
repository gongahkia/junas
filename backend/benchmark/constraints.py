"""IFEval-style constraint runners for ConstraintSatisfaction evaluator.

Each constraint is a small Python function returning True / False. Used by
``benchmark.evaluators.ConstraintSatisfaction`` and the SGLB-15 task.

To add a new constraint kind, write a function and register it in
``CONSTRAINTS``. Unit tests live in ``tests/test_benchmark_constraints.py``.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from api.services.sal_citation import validate_citation

ConstraintRunner = Callable[[str, dict[str, Any]], bool]


def _named_party_present(output: str, params: dict[str, Any]) -> bool:
    names = params.get("party_names", []) or []
    if not names:
        return True
    return all(str(name) in (output or "") for name in names)


def _governing_law_singapore(output: str, params: dict[str, Any]) -> bool:
    del params
    pattern = re.compile(r"governed\s+by.*?Singapore|Singapore\s+law\s+governs", re.IGNORECASE)
    return bool(pattern.search(output or ""))


def _citation_format_valid(output: str, params: dict[str, Any]) -> bool:
    del params
    candidates = re.findall(r"\[\d{4}\]\s+\S+\s+\d+(?:[^\s.]*)?", output or "")
    if not candidates:
        return True
    return all(validate_citation(c).valid for c in candidates)


def _required_section_present(output: str, params: dict[str, Any]) -> bool:
    heading = str(params.get("heading", "")).strip()
    min_words = int(params.get("min_words", 100))
    if not heading:
        return True
    # Find a markdown heading line containing the required heading.
    pattern = re.compile(
        rf"^#+\s*.*{re.escape(heading)}.*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(output or "")
    if not match:
        return False
    # Body starts after the heading; ends at the next heading of equal-or-higher level.
    after = (output or "")[match.end() :]
    next_heading = re.search(r"^#+\s", after, re.MULTILINE)
    body = after[: next_heading.start()] if next_heading else after
    return len(body.split()) >= min_words


def _min_word_count(output: str, params: dict[str, Any]) -> bool:
    return len((output or "").split()) >= int(params.get("min_words", 1))


def _iso_date_present(output: str, params: dict[str, Any]) -> bool:
    del params
    return bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b", output or ""))


def _sgd_amount_present(output: str, params: dict[str, Any]) -> bool:
    del params
    return bool(re.search(r"\bSGD\s+[\d,]+(?:\.\d+)?\b", output or ""))


def _no_forbidden_phrase(output: str, params: dict[str, Any]) -> bool:
    phrases = params.get("phrases", []) or []
    text = (output or "").lower()
    return not any(str(p).lower() in text for p in phrases)


CONSTRAINTS: dict[str, ConstraintRunner] = {
    "named_party_present": _named_party_present,
    "governing_law_singapore": _governing_law_singapore,
    "citation_format_valid": _citation_format_valid,
    "required_section_present": _required_section_present,
    "min_word_count": _min_word_count,
    "iso_date_present": _iso_date_present,
    "sgd_amount_present": _sgd_amount_present,
    "no_forbidden_phrase": _no_forbidden_phrase,
}


def register_constraint(name: str, runner: ConstraintRunner) -> None:
    CONSTRAINTS[name] = runner

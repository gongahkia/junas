"""SGLB-15 Draft-Constraint-Sat synthetic task wrapper."""
from __future__ import annotations

from benchmark.registry import register_task
from benchmark.schema import Case


def _require_reviewed(case: Case) -> None:
    if case.metadata.get("data_tier") != "synthetic" or case.metadata.get("review_stage") != "reviewed":
        raise ValueError("SGLB-15 reads reviewed synthetic fixtures only")


def _words(count: int) -> str:
    return " ".join(f"term{i}" for i in range(max(0, count)))


async def sglb_15_task(case: Case) -> str:
    _require_reviewed(case)
    constraints = (case.expected_output or {}).get("constraints", [])
    party_names: list[str] = []
    headings: list[tuple[str, int]] = []
    min_words = 80
    forbidden: set[str] = set()

    for constraint in constraints:
        params = constraint.get("params", {}) or {}
        kind = constraint.get("kind")
        if kind == "named_party_present":
            party_names.extend(str(name) for name in params.get("party_names", []) or [])
        elif kind == "required_section_present":
            headings.append((str(params.get("heading") or "Required Terms"), int(params.get("min_words", 40))))
        elif kind == "min_word_count":
            min_words = max(min_words, int(params.get("min_words", min_words)))
        elif kind == "no_forbidden_phrase":
            forbidden.update(str(phrase).lower() for phrase in params.get("phrases", []) or [])

    if not party_names:
        party_names = ["Acme Pte Ltd", "Beacon Pte Ltd"]
    heading_blocks = []
    for heading, words in headings:
        heading_blocks.append(f"## {heading}\n{_words(words + 5)}")
    if not heading_blocks:
        heading_blocks.append("## General Terms\nThe parties will cooperate in good faith under this agreement.")

    body = (
        "# Synthetic Draft\n\n"
        f"This Agreement is between {', '.join(party_names)} and is dated 2026-06-03.\n\n"
        "This Agreement is governed by the laws of Singapore. The contract value is SGD 1,000.\n\n"
        + "\n\n".join(heading_blocks)
        + "\n\n"
        + _words(min_words + 10)
    )
    for phrase in forbidden:
        body = body.replace(phrase, "reasonable efforts")
    return body


register_task("sglb_15", sglb_15_task)

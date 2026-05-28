#!/usr/bin/env python3
"""Verify the integrity of the Kaypoh review journal.

Recomputes every HMAC and prev_hash link in `${KAYPOH_JOURNAL_DIR:-./kaypoh-journal}/journal.jsonl`.
Exit 0 if the chain is intact, 1 if any tamper is detected.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.journal import journal_path, read_journal, verify_chain  # noqa: E402


def _identity_source_warnings(entries) -> list[str]:
    sources_by_review: dict[str, set[str]] = {}
    for entry in entries:
        if entry.event_type != "decision_recorded":
            continue
        source = str(entry.payload.get("reviewer_identity_source", "") or "")
        if not source:
            source = "legacy" if entry.payload.get("reviewer_id") else "none"
        sources_by_review.setdefault(entry.review_id, set()).add(source)
    warnings: list[str] = []
    for review_id, sources in sorted(sources_by_review.items()):
        if len(sources) > 1:
            warnings.append(
                f"review {review_id} has mixed reviewer identity sources: {', '.join(sorted(sources))}"
            )
    return warnings


def main() -> int:
    entries = read_journal()
    if not entries:
        print(f"journal at {journal_path()} is empty or missing")
        return 0
    valid, errors = verify_chain(entries)
    warnings = _identity_source_warnings(entries)
    print(f"entries: {len(entries)}")
    print(f"chain: {'valid' if valid else 'tampered'}")
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

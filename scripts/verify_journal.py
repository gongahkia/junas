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


def main() -> int:
    entries = read_journal()
    if not entries:
        print(f"journal at {journal_path()} is empty or missing")
        return 0
    valid, errors = verify_chain(entries)
    print(f"entries: {len(entries)}")
    print(f"chain: {'valid' if valid else 'tampered'}")
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

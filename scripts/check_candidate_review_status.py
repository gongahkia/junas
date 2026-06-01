#!/usr/bin/env python3
"""Check that candidate or auto-labeled fixtures have human approval."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.candidate_review import (  # noqa: E402
    collect_review_status_violations,
    collect_stage_b_readiness_violations,
)

DEFAULT_CORPUS = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Require human approval for candidate/auto labels")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--require-stage-b-ready", action="store_true")
    args = parser.parse_args(argv)

    corpus = args.corpus if args.corpus.is_absolute() else REPO_ROOT / args.corpus
    if not corpus.exists():
        print(f"corpus missing: {corpus}", file=sys.stderr)
        return 2
    violations = collect_review_status_violations(corpus)
    if args.require_stage_b_ready:
        violations.extend(collect_stage_b_readiness_violations(corpus))
    for violation in violations:
        print(f"review-status violation: {violation}", file=sys.stderr)
    print(f"checked {corpus}: violations={len(violations)}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

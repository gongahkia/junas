#!/usr/bin/env python3
"""Require promoted-corpus lock updates when reviewed fixture inputs change."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMOTED_CORPUS_DIR = Path("test/fixtures/legal-corpus-reviewed-candidates")
PROMOTED_LOCK = PROMOTED_CORPUS_DIR / "legal-corpus-reviewed-candidates.lock.json"
ACCURACY_DOC = Path("docs/accuracy.md")


def _normalize(path: str | Path) -> str:
    return Path(path).as_posix().lstrip("./")


def is_promoted_fixture_input(path: str | Path) -> bool:
    normalized = _normalize(path)
    prefix = f"{PROMOTED_CORPUS_DIR.as_posix()}/"
    return normalized.startswith(prefix) and (
        normalized.endswith(".txt") or normalized.endswith(".labels.json")
    )


def evaluate_changed_paths(changed_paths: list[str]) -> dict[str, Any]:
    changed = {_normalize(path) for path in changed_paths}
    promoted_inputs = sorted(path for path in changed if is_promoted_fixture_input(path))
    required = {_normalize(PROMOTED_LOCK), _normalize(ACCURACY_DOC)}
    missing = sorted(required - changed) if promoted_inputs else []
    return {
        "ok": not missing,
        "promoted_inputs": promoted_inputs,
        "required_updates": sorted(required) if promoted_inputs else [],
        "missing_updates": missing,
    }


def changed_paths_from_git(base_ref: str, head_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", base_ref, head_ref],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git diff failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail when promoted reviewed-corpus fixtures change without refreshed locks"
    )
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", default="HEAD")
    args = parser.parse_args(argv)

    try:
        changed = changed_paths_from_git(args.base_ref, args.head_ref)
    except RuntimeError as exc:
        print(f"promoted lock freshness check failed: {exc}", file=sys.stderr)
        return 2

    result = evaluate_changed_paths(changed)
    if result["ok"]:
        if result["promoted_inputs"]:
            print("promoted fixture inputs changed; lock and accuracy doc updates are present")
        else:
            print("no promoted fixture input changes")
        return 0

    print("promoted fixture inputs changed without required lock/doc updates:", file=sys.stderr)
    for path in result["promoted_inputs"]:
        print(f"changed input: {path}", file=sys.stderr)
    for path in result["missing_updates"]:
        print(f"missing update: {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Report candidate strict-label deltas against current strict runtime findings."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from junas.review.engine import PreSendReviewEngine  # noqa: E402
from scripts.candidate_review import collect_review_status_violations, labels_path_for, load_labels  # noqa: E402

DEFAULT_CORPUS = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _resolve_actor() -> str:
    try:
        out = subprocess.run(
            ["git", "config", "--get", "user.email"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _run_findings(text: str, labels: dict[str, Any]) -> list[dict[str, str]]:
    result = PreSendReviewEngine().review(
        text=text,
        source_jurisdiction=str(labels.get("source_jurisdiction") or "SG"),
        destination_jurisdiction=str(labels.get("destination_jurisdiction") or "SG"),
        entity_id=None,
        include_suggestions=False,
        document_type=str(labels.get("document_type") or "generic"),
        review_profile="strict",
    )
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for finding in result.findings:
        key = (finding.rule, finding.matched_text)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "category": finding.category,
            "rule": finding.rule,
            "matched_text": finding.matched_text,
        })
    return out


def _ideal_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("rule") or ""), str(item.get("matched_text") or ""))


def reconcile_strict_labels(
    *,
    corpus: Path,
    dry_run: bool = False,
    actor: str = "",
    reason: str = "",
    require_human_reviewed: bool = False,
) -> dict[str, Any]:
    if require_human_reviewed:
        violations = collect_review_status_violations(corpus)
        if violations:
            return {
                "corpus": str(corpus),
                "dry_run": dry_run,
                "blocked": True,
                "human_review_violations": violations,
            }
    actor = actor or _resolve_actor()
    changed: list[dict[str, Any]] = []
    totals = {
        "scanned": 0,
        "fixtures_with_runtime_delta": 0,
        "runtime_findings_not_in_must_detect": 0,
        "stale_must_detect_not_emitted": 0,
    }
    for txt_path in sorted(corpus.glob("**/*.txt")):
        labels_path = labels_path_for(txt_path)
        if not labels_path.exists():
            continue
        totals["scanned"] += 1
        labels = load_labels(labels_path)
        runtime = _run_findings(txt_path.read_text(encoding="utf-8"), labels)
        runtime_keys = {(item["rule"], item["matched_text"]) for item in runtime}
        must = list(labels.get("must_detect") or [])
        existing_keys = {_ideal_key(item) for item in must}

        runtime_not_labeled = [
            finding
            for finding in runtime
            if (finding["rule"], finding["matched_text"]) not in existing_keys
        ]
        stale_must = [
            item
            for item in must
            if _ideal_key(item) not in runtime_keys
        ]

        if not runtime_not_labeled and not stale_must:
            continue
        changed.append({
            "fixture": _display_path(txt_path),
            "labels": _display_path(labels_path),
            "runtime_findings_not_in_must_detect": runtime_not_labeled,
            "stale_must_detect_not_emitted": stale_must,
        })
        totals["fixtures_with_runtime_delta"] += 1
        totals["runtime_findings_not_in_must_detect"] += len(runtime_not_labeled)
        totals["stale_must_detect_not_emitted"] += len(stale_must)
    return {
        "corpus": str(corpus),
        "dry_run": dry_run,
        "actor": actor,
        "reason": reason,
        "labels_mutated": False,
        "blocked": False,
        **totals,
        "changed_fixtures": changed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report candidate strict-label deltas against runtime findings")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--actor", default="", help="Attribution recorded in label metadata")
    parser.add_argument("--reason", default="", help="Required audit note for this delta report")
    parser.add_argument("--require-human-reviewed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.reason.strip():
        print("--reason is required", file=sys.stderr)
        return 2
    corpus = args.corpus if args.corpus.is_absolute() else REPO_ROOT / args.corpus
    if not corpus.exists():
        print(f"candidate corpus missing: {corpus}", file=sys.stderr)
        return 2
    result = reconcile_strict_labels(
        corpus=corpus,
        dry_run=args.dry_run,
        actor=args.actor,
        reason=args.reason.strip(),
        require_human_reviewed=args.require_human_reviewed,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result.get("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())

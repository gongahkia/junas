#!/usr/bin/env python3
"""Promote human-approved candidate fixtures into a reviewed corpus."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.candidate_review import (  # noqa: E402
    approved_reviewed_at,
    approved_reviewer,
    detector_provenance_violations,
    is_human_approved,
    labels_path_for,
    load_labels,
    utc_now,
    write_labels,
)

DEFAULT_CANDIDATE_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"
DEFAULT_TARGET = REPO_ROOT / "test" / "fixtures" / "legal-corpus-reviewed-candidates"
MANIFEST_NAME = "candidate_promotion_manifest.jsonl"


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _promotion_entry(
    *,
    source_txt: Path,
    target_txt: Path,
    labels: dict[str, Any],
    promoted_at: str,
) -> dict[str, Any]:
    return {
        "promoted_at_utc": promoted_at,
        "source_fixture": _relative(source_txt),
        "target_fixture": _relative(target_txt),
        "doc_id": labels.get("doc_id"),
        "source_jurisdiction": labels.get("source_jurisdiction"),
        "destination_jurisdiction": labels.get("destination_jurisdiction"),
        "taxonomy_concept": labels.get("_taxonomy_concept"),
        "label_source": labels.get("_label_source"),
        "label_model": labels.get("_label_model"),
        "reviewer": approved_reviewer(labels),
        "reviewed_at_utc": approved_reviewed_at(labels),
    }


def promote_candidates(
    *,
    candidate_dir: Path,
    target_dir: Path,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    candidate_dir = candidate_dir.resolve()
    target_dir = target_dir.resolve()
    promoted_at = utc_now()
    promoted: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    errors: list[str] = []
    for source_txt in sorted(candidate_dir.glob("**/*.txt")):
        labels_path = labels_path_for(source_txt)
        if not labels_path.exists():
            skipped.append({"fixture": _relative(source_txt), "reason": "missing_labels"})
            continue
        labels = load_labels(labels_path)
        if not is_human_approved(labels):
            skipped.append({
                "fixture": _relative(source_txt),
                "reason": f"not_approved:{labels.get('_human_review_status', 'missing')}",
            })
            continue
        provenance_violations = detector_provenance_violations(labels_path, labels)
        if provenance_violations:
            errors.extend(
                f"detector-derived label provenance blocks promotion: {item}"
                for item in provenance_violations
            )
            continue
        target_txt = target_dir / source_txt.name
        target_labels = target_dir / labels_path.name
        if not force and (target_txt.exists() or target_labels.exists()):
            errors.append(f"refusing to overwrite existing target: {target_txt} / {target_labels}")
            continue
        entry = _promotion_entry(source_txt=source_txt, target_txt=target_txt, labels=labels, promoted_at=promoted_at)
        promoted.append(entry)
        if dry_run:
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_txt, target_txt)
        target_payload = dict(labels)
        target_payload["_promotion"] = entry
        write_labels(target_labels, target_payload)
        with (target_dir / MANIFEST_NAME).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
    return {
        "candidate_dir": str(candidate_dir),
        "target_dir": str(target_dir),
        "promoted": promoted,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote approved candidate fixtures")
    parser.add_argument("--candidate-dir", type=Path, default=DEFAULT_CANDIDATE_DIR)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    candidate_dir = args.candidate_dir if args.candidate_dir.is_absolute() else REPO_ROOT / args.candidate_dir
    target_dir = args.target if args.target.is_absolute() else REPO_ROOT / args.target
    if not candidate_dir.exists():
        print(f"candidate dir missing: {candidate_dir}", file=sys.stderr)
        return 2
    try:
        result = promote_candidates(
            candidate_dir=candidate_dir,
            target_dir=target_dir,
            force=args.force,
            dry_run=args.dry_run,
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"promotion failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

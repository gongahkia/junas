#!/usr/bin/env python3
"""Check the reviewed-candidate conjunctive MNPI provenance sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.candidate_review import label_item_has_detector_provenance, labels_have_detector_source  # noqa: E402

DEFAULT_CORPUS = REPO_ROOT / "test" / "fixtures" / "legal-corpus-reviewed-candidates"
DEFAULT_OUTPUT = DEFAULT_CORPUS / "mnpi_conjunctive_label_provenance.json"
RULE = "conjunctive_mnpi"
SECTIONS = ("must_detect", "ideal_must_detect", "must_not_detect", "uncertain")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _reviewer(labels: dict[str, Any]) -> str:
    review = labels.get("_human_review")
    if isinstance(review, dict) and str(review.get("reviewer") or "").strip():
        return str(review["reviewer"])
    promotion = labels.get("_promotion")
    if isinstance(promotion, dict) and str(promotion.get("reviewer") or "").strip():
        return str(promotion["reviewer"])
    return ""


def _iter_label_items(corpus: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for labels_path in sorted(corpus.glob("*.labels.json")):
        labels = _load_json(labels_path)
        rel_path = labels_path.relative_to(REPO_ROOT).as_posix()
        reviewer = _reviewer(labels)
        status = str(labels.get("_human_review_status") or "")
        for section in SECTIONS:
            items = labels.get(section)
            if not isinstance(items, list):
                continue
            for idx, item in enumerate(items):
                if not isinstance(item, dict) or item.get("rule") != RULE:
                    continue
                records.append(
                    {
                        "doc_id": str(labels.get("doc_id") or labels_path.stem.removesuffix(".labels")),
                        "document_type": str(labels.get("document_type") or ""),
                        "file": rel_path,
                        "has_detector_item_provenance": label_item_has_detector_provenance(item),
                        "has_detector_label_source": labels_have_detector_source(labels),
                        "reviewer": reviewer,
                        "review_status": status,
                        "section": section,
                        "source_jurisdiction": str(labels.get("source_jurisdiction") or ""),
                        "taxonomy_concept": str(labels.get("_taxonomy_concept") or ""),
                        "index": idx,
                    }
                )
    return records


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def build_manifest(corpus: Path = DEFAULT_CORPUS) -> dict[str, Any]:
    records = _iter_label_items(corpus)
    if not records:
        raise ValueError(f"no {RULE} labels found in {corpus}")
    files = {record["file"] for record in records}
    reviewers = Counter(record["reviewer"] for record in records)
    statuses = Counter(record["review_status"] for record in records)
    sections = Counter(record["section"] for record in records)
    detector_items = sum(1 for record in records if record["has_detector_item_provenance"])
    detector_sources = sum(1 for record in records if record["has_detector_label_source"])
    digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "rule": RULE,
        "corpus": corpus.relative_to(REPO_ROOT).as_posix(),
        "scope": "all reviewed-candidate label items whose rule is conjunctive_mnpi",
        "counts": {
            "label_files": len(files),
            "label_items": len(records),
            "section_counts": _counter_dict(sections),
            "detector_reconciled_label_items": detector_items,
            "detector_label_source_items": detector_sources,
            "non_detector_item_provenance_items": len(records) - detector_items,
        },
        "non_detector_author_provenance": {
            "basis": "file-level _human_review/_promotion metadata records project-owner manual review",
            "review_status_counts": _counter_dict(statuses),
            "reviewer_counts": _counter_dict(reviewers),
        },
        "independence_disclosure": (
            "Strict conjunctive_mnpi must_detect span placement is detector-reconciled and must not be "
            "presented as an independent public MNPI benchmark; use it as internal project-owner-reviewed "
            "fixture evidence only."
        ),
        "source_review": {
            "reviewed_on": "2026-07-01",
            "result": "No public MNPI text-detection benchmark comparable to TAB or ai4privacy was identified.",
            "queries": [
                "public MNPI text detection corpus material nonpublic information benchmark dataset",
                "material nonpublic information dataset text classification corpus MNPI",
                "inside information dataset material non-public text detection corpus",
            ],
            "contrast_public_pii_benchmarks": [
                "https://github.com/NorskRegnesentral/text-anonymization-benchmark",
                "https://arxiv.org/abs/2604.15776",
            ],
        },
        "record_sha256": digest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    corpus = args.corpus if args.corpus.is_absolute() else REPO_ROOT / args.corpus
    manifest_path = args.manifest if args.manifest.is_absolute() else REPO_ROOT / args.manifest
    expected = build_manifest(corpus)
    rendered = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    if args.write:
        manifest_path.write_text(rendered, encoding="utf-8")
        print(f"wrote {manifest_path.relative_to(REPO_ROOT)}")
        return 0
    if not manifest_path.exists():
        print(f"missing manifest: {manifest_path.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 2
    actual = manifest_path.read_text(encoding="utf-8")
    if actual != rendered:
        print(f"stale manifest: {manifest_path.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1
    print(f"ok {manifest_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

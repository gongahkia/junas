#!/usr/bin/env python3
"""Generate a quick data-quality report for docs/json training corpus."""

import json
import sys
import argparse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.schemas import TrainingDocument


def percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    idx = int(round((pct / 100.0) * (len(values_sorted) - 1)))
    idx = max(0, min(idx, len(values_sorted) - 1))
    return float(values_sorted[idx])


def parse_args():
    parser = argparse.ArgumentParser(description="Generate training corpus quality report")
    parser.add_argument("--warn-label-min-pct", type=float, default=10.0, help="Warn if any label falls below this percentage")
    parser.add_argument("--warn-duplicate-ratio", type=float, default=0.2, help="Warn if duplicate text ratio exceeds this value")
    parser.add_argument("--warn-p95-length", type=int, default=400, help="Warn if p95 sentence length exceeds this")
    parser.add_argument("--strict-warnings", action="store_true", help="Return non-zero when warnings are present")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = Path(__file__).parent.parent / "docs" / "json"
    files = sorted(data_dir.glob("*.json"))
    if not files:
        print("[FAIL] No JSON files found in docs/json")
        return 1

    label_counts: Counter[str] = Counter()
    sentence_counts: Counter[str] = Counter()
    sentence_lengths: list[int] = []
    docs_ok = 0
    docs_fail = 0

    for fp in files:
        try:
            raw = json.loads(fp.read_text())
            doc = TrainingDocument.model_validate(raw)
            docs_ok += 1
        except Exception as e:
            docs_fail += 1
            print(f"[FAIL] {fp.name}: {e}")
            continue

        for sent in doc.document_sentence_array:
            label_counts[sent.label] += 1
            normalized = " ".join(sent.text.lower().split())
            sentence_counts[normalized] += 1
            sentence_lengths.append(len(sent.text))

    dup_sentences = sum(1 for _, count in sentence_counts.items() if count > 1)
    total_sentences = sum(label_counts.values())
    duplicate_ratio = (dup_sentences / total_sentences) if total_sentences else 0.0
    avg_len = (sum(sentence_lengths) / len(sentence_lengths)) if sentence_lengths else 0.0
    p95_len = percentile(sentence_lengths, 95.0)
    warnings = []

    print("=== Data Quality Report ===")
    print(f"documents_total   : {len(files)}")
    print(f"documents_valid   : {docs_ok}")
    print(f"documents_invalid : {docs_fail}")
    print(f"sentences_total   : {total_sentences}")
    print("label_distribution:")
    for label in ("non", "low", "high"):
        count = label_counts.get(label, 0)
        pct = (count / total_sentences * 100.0) if total_sentences else 0.0
        print(f"  - {label}: {count} ({pct:.2f}%)")
        if pct < args.warn_label_min_pct:
            warnings.append(
                f"label '{label}' underrepresented: {pct:.2f}% < {args.warn_label_min_pct:.2f}%"
            )
    print(f"duplicate_sentence_texts: {dup_sentences}")
    print(f"duplicate_ratio         : {duplicate_ratio:.4f}")
    print(f"sentence_length_mean    : {avg_len:.2f}")
    print(f"sentence_length_p95     : {p95_len:.2f}")

    if duplicate_ratio > args.warn_duplicate_ratio:
        warnings.append(
            f"duplicate ratio high: {duplicate_ratio:.4f} > {args.warn_duplicate_ratio:.4f}"
        )
    if p95_len > args.warn_p95_length:
        warnings.append(
            f"p95 sentence length high: {p95_len:.2f} > {args.warn_p95_length}"
        )

    if warnings:
        print("warnings:")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("warnings: none")

    if docs_fail > 0:
        return 1
    if args.strict_warnings and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

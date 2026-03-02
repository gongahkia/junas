#!/usr/bin/env python3
"""Generate a quick data-quality report for docs/json training corpus."""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.schemas import TrainingDocument


def main() -> int:
    data_dir = Path(__file__).parent.parent / "docs" / "json"
    files = sorted(data_dir.glob("*.json"))
    if not files:
        print("[FAIL] No JSON files found in docs/json")
        return 1

    label_counts: Counter[str] = Counter()
    sentence_counts: Counter[str] = Counter()
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

    dup_sentences = sum(1 for _, count in sentence_counts.items() if count > 1)
    total_sentences = sum(label_counts.values())

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
    print(f"duplicate_sentence_texts: {dup_sentences}")

    if docs_fail > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


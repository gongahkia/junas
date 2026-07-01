#!/usr/bin/env python3
"""Run TAB singling-out validation for selected jurisdiction packs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from scripts.run_tab_eval import DEFAULT_TAB_DIR, TAB_SPLIT_FILES, _git_commit, evaluate_tab  # noqa: E402

DEFAULT_OUTPUT = REPO_ROOT / "reports" / "current" / "singling_out_pack_eval_20260701.json"
DEFAULT_PACKS = ("SG", "US", "UK")
SCHEMA_VERSION = "junas.singling_out_pack_eval.v1"


def compact_tab_report(report: dict[str, Any]) -> dict[str, Any]:
    validation = report["singling_out_validation"]
    qic_score = validation["quasi_identifier_combination_overlap_score"]
    return {
        "summary": report["summary"],
        "quasi_identifier_type_score": report["by_identifier_type"]["QUASI"],
        "singling_out": {
            "gold_quasi_spans": validation["gold_quasi_spans"],
            "gold_quasi_docs": validation["gold_quasi_docs"],
            "gold_quasi_coreference_groups": validation["gold_quasi_coreference_groups"],
            "gold_quasi_coreference_spans": validation["gold_quasi_coreference_spans"],
            "quasi_identifier_combination_predictions": validation["quasi_identifier_combination_predictions"],
            "quasi_identifier_combination_docs": validation["quasi_identifier_combination_docs"],
            "quasi_identifier_combination_precision": qic_score["precision"],
            "quasi_identifier_combination_recall": qic_score["recall"],
            "quasi_identifier_combination_f2": qic_score["f2"],
        },
        "prediction_rule_counts": report["prediction_rule_counts"],
    }


def evaluate_packs(tab_dir: Path, packs: list[str], splits: list[str]) -> dict[str, Any]:
    pack_reports: dict[str, Any] = {}
    for pack in packs:
        report = evaluate_tab(
            tab_dir=tab_dir,
            splits=splits,
            review_profile="strict",
            source_jurisdiction=pack,
            destination_jurisdiction=pack,
            categories={"PII"},
            match_mode="overlap",
        )
        pack_reports[pack] = compact_tab_report(report)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "name": "Text Anonymization Benchmark",
            "fixture_path": str(tab_dir.relative_to(REPO_ROOT) if tab_dir.is_relative_to(REPO_ROOT) else tab_dir),
            "fixture_commit": _git_commit(tab_dir),
            "splits": splits,
            "gold_label_source": "TAB QUASI annotations and entity_id co-reference groups",
        },
        "evaluation": {
            "review_profile": "strict",
            "finding_categories": ["PII"],
            "match_mode": "overlap",
            "packs": packs,
            "never_updates_promotion_lock": True,
        },
        "packs": pack_reports,
        "decision": {
            "status": "deepen_sg_us_uk_before_widening",
            "rationale": (
                "SG, US, and UK have bundled frequency tables and dense recognizer coverage; thin packs "
                "should not receive more quasi-ID expansion until these three packs show stable TAB "
                "QUASI/coreference behavior and candidate-corpus singling_out_miss reduction."
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tab-dir", type=Path, default=DEFAULT_TAB_DIR)
    parser.add_argument("--packs", nargs="+", default=list(DEFAULT_PACKS))
    parser.add_argument("--splits", nargs="+", choices=tuple(TAB_SPLIT_FILES), default=list(TAB_SPLIT_FILES))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    tab_dir = args.tab_dir if args.tab_dir.is_absolute() else REPO_ROOT / args.tab_dir
    if not tab_dir.is_dir():
        print(f"missing TAB fixture at {tab_dir}; run scripts/fetch_tab_fixture.sh first", file=sys.stderr)
        return 2
    payload = evaluate_packs(tab_dir, [pack.upper() for pack in args.packs], list(args.splits))
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for pack, report in payload["packs"].items():
        score = report["singling_out"]
        print(
            f"{pack} qic predictions={score['quasi_identifier_combination_predictions']} "
            f"recall={score['quasi_identifier_combination_recall']:.6f} "
            f"f2={score['quasi_identifier_combination_f2']:.6f}"
        )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

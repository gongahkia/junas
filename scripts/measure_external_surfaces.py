"""Measure legacy findings and contextual PII separately against external masking labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from junas.review.engine import PreSendReviewEngine  # noqa: E402
from scripts import model_corpus as corpus  # noqa: E402
from scripts.fresh_holdout import runtime_hash  # noqa: E402
from scripts.run_ai4privacy_eval import evaluate_ai4privacy  # noqa: E402
from scripts.run_tab_eval import evaluate_tab  # noqa: E402


class ContextualPiiEngine:
    """Adapt contextual evidence without changing either evaluator's matching contract."""

    def __init__(self) -> None:
        self.engine = PreSendReviewEngine()

    def review(self, **kwargs):
        result = self.engine.review(**kwargs)
        return SimpleNamespace(
            findings=[SimpleNamespace(category="PII", **item) for item in result.sensitivity["pii"]["evidence"]],
            degraded_modes=result.degraded_modes,
        )


def measure(tab_dir: Path, fixture: Path, manifest: Path, output: Path) -> dict:
    corpus.require(not output.exists(), "new output directory required; preserve prior measurements")
    output.mkdir(parents=True)
    reports = {}
    for surface, factory in (("findings", PreSendReviewEngine), ("contextual_pii", ContextualPiiEngine)):
        for dataset, report in (
            ("tab_dev", evaluate_tab(tab_dir=tab_dir, splits=["dev"], engine_factory=factory)),
            ("ai4privacy", evaluate_ai4privacy(fixture=fixture, manifest_path=manifest, engine_factory=factory)),
        ):
            report["prediction_surface"] = surface
            report["classifier_runtime_sha256"] = runtime_hash(ROOT)
            report["scope"] = (
                "external masking-label agreement; no approved entity-type crosswalk; "
                "no MNPI accuracy or calibrated confidence; not a new protected holdout"
            )
            name = f"{dataset}-{surface}.json"
            corpus.write_new(output / name, report)
            reports[name] = corpus.identity(report)
    summary = {
        "reports": reports,
        "tab_splits_evaluated": ["dev"],
        "classifier_runtime_sha256": runtime_hash(ROOT),
        "paid_api_calls": 0,
        "labels_changed": False,
        "surfaces_pooled": False,
    }
    corpus.write_new(output / "manifest.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tab-dir", type=Path, required=True)
    parser.add_argument("--ai4privacy-fixture", type=Path, required=True)
    parser.add_argument("--ai4privacy-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.tab_dir, args.ai4privacy_fixture, args.ai4privacy_manifest, args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

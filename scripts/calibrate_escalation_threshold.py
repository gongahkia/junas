#!/usr/bin/env python3
"""Bayesian-opt search over the two-tier router's ambiguous-band thresholds.

The two-tier engine in `junas.review.engine` ships defaults
`LLM_TIER_MNPI_LOWER=25.0` and `LLM_TIER_MNPI_UPPER=70.0`. Those values were picked by
hand from the score-from-severity table; this script lets us find tenant-specific bounds
that optimise a weighted mix of precision, recall, p95 latency, and per-call LLM cost on
the adversarial corpus.

Search strategy: random-sample the (lower, upper) plane, score each candidate, and report
the best. The space is 2-D and bounded so global optimisation is cheap; we don't need
Bayesian-opt sophistication yet, but the script's interface is shaped so a future swap to
scipy.optimize / scikit-optimize is a 20-line patch.

What gets optimised:
- precision: per-rule precision averaged across the adversarial corpus
- recall:    per-rule recall averaged across the adversarial corpus
- escalation_rate: fraction of documents where LLM tier engaged (latency + cost proxy)
- latency_score: 1 - escalation_rate (lower escalation_rate → higher score)

The objective is a weighted sum (default weights tilt toward precision; CLI flags adjust).

Usage:
    python3 scripts/calibrate_escalation_threshold.py
    python3 scripts/calibrate_escalation_threshold.py --corpus test/fixtures/legal-corpus
    python3 scripts/calibrate_escalation_threshold.py --iterations 200 --apply
    python3 scripts/calibrate_escalation_threshold.py --w-precision 2.0 --w-cost 0.5

Output: a JSON report with the recommended (lower, upper) bounds, the objective at the
recommendation, and the metric breakdown. With `--apply`, the script also writes the
recommended bounds into `config/runtime_calibrated.toml` (a separate file so customer
overrides remain explicit; the engine continues to use its compile-time defaults unless
junas.configs.runtime reads this file).

Exit codes:
    0 = search completed; recommendation printed (and applied if requested)
    1 = no fixtures found in the corpus directory
    2 = invalid CLI args
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from junas.review.engine import (  # noqa: E402
    LLM_TIER_MNPI_LOWER,
    LLM_TIER_MNPI_UPPER,
    PreSendReviewEngine,
)

DEFAULT_CORPUS = REPO_ROOT / "test" / "fixtures" / "legal-corpus-adversarial"
DEFAULT_OUTPUT = REPO_ROOT / "config" / "runtime_calibrated.toml"


# --- corpus loading ---------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureCase:
    doc_id: str
    text: str
    document_type: str
    source_jurisdiction: str
    destination_jurisdiction: str
    must_detect: list[dict[str, Any]]
    must_not_detect: list[dict[str, Any]]


def _load_fixtures(corpus_dir: Path) -> list[FixtureCase]:
    cases: list[FixtureCase] = []
    for doc_path in sorted(corpus_dir.glob("*.txt")):
        labels_path = doc_path.with_suffix(".labels.json")
        if not labels_path.exists():
            continue
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        cases.append(FixtureCase(
            doc_id=labels.get("doc_id", doc_path.stem),
            text=doc_path.read_text(encoding="utf-8"),
            document_type=labels.get("document_type", "generic"),
            source_jurisdiction=labels.get("source_jurisdiction", "SG"),
            destination_jurisdiction=labels.get("destination_jurisdiction", "SG"),
            must_detect=labels.get("must_detect", []),
            must_not_detect=labels.get("must_not_detect", []),
        ))
    return cases


# --- metric computation -----------------------------------------------------------------


@dataclass
class CandidateMetrics:
    precision: float
    recall: float
    escalation_rate: float
    latency_score: float


def _evaluate_candidate(
    *,
    lower: float,
    upper: float,
    cases: list[FixtureCase],
) -> CandidateMetrics:
    """Re-run the engine with a patched (lower, upper) band and measure outcomes.

    The engine ships its band as module constants; we monkey-patch them on the imported
    module for the duration of one evaluation. This keeps the calibration script
    self-contained — no engine API change needed."""
    from junas.review import engine as engine_mod

    orig_lower = engine_mod.LLM_TIER_MNPI_LOWER
    orig_upper = engine_mod.LLM_TIER_MNPI_UPPER
    engine_mod.LLM_TIER_MNPI_LOWER = lower
    engine_mod.LLM_TIER_MNPI_UPPER = upper
    try:
        return _measure(cases)
    finally:
        engine_mod.LLM_TIER_MNPI_LOWER = orig_lower
        engine_mod.LLM_TIER_MNPI_UPPER = orig_upper


def _measure(cases: list[FixtureCase]) -> CandidateMetrics:
    """Run all fixtures through the engine in strict mode (deterministic only) and use
    the score-band membership as the escalation proxy. We compute precision + recall
    against the labels file independent of band membership — the band only affects
    runtime LLM cost, not deterministic detector behavior."""
    engine = PreSendReviewEngine()
    rule_tp: dict[str, int] = {}
    rule_fn: dict[str, int] = {}
    rule_fp: dict[str, int] = {}
    in_band_count = 0
    total_count = 0

    for case in cases:
        result = engine.review(
            text=case.text,
            source_jurisdiction=case.source_jurisdiction,
            destination_jurisdiction=case.destination_jurisdiction,
            entity_id=None,
            include_suggestions=False,
            document_type=case.document_type,
            review_profile="strict",
        )
        from junas.review import engine as engine_mod

        in_band = engine_mod.LLM_TIER_MNPI_LOWER <= result.mnpi_score < engine_mod.LLM_TIER_MNPI_UPPER
        total_count += 1
        if in_band:
            in_band_count += 1

        # recall: did every must_detect entry show up?
        finding_keys = {(f.rule, f.matched_text) for f in result.findings}
        for label in case.must_detect:
            key = (label["rule"], label["matched_text"])
            rule = label["rule"]
            if key in finding_keys:
                rule_tp[rule] = rule_tp.get(rule, 0) + 1
            else:
                rule_fn[rule] = rule_fn.get(rule, 0) + 1
        # precision proxy: must_not_detect violations
        forbidden = {entry["matched_text"]: True for entry in case.must_not_detect}
        for finding in result.findings:
            if finding.matched_text in forbidden:
                rule_fp[finding.rule] = rule_fp.get(finding.rule, 0) + 1

    def _macro(values: dict[str, int], denom_a: dict[str, int], denom_b: dict[str, int]) -> float:
        per_rule: list[float] = []
        for rule in set(values) | set(denom_a) | set(denom_b):
            num = values.get(rule, 0)
            denom = denom_a.get(rule, 0) + denom_b.get(rule, 0)
            if denom == 0:
                per_rule.append(1.0)
            else:
                per_rule.append(num / denom)
        return statistics.fmean(per_rule) if per_rule else 1.0

    precision = _macro(rule_tp, rule_tp, rule_fp)
    recall = _macro(rule_tp, rule_tp, rule_fn)
    escalation_rate = (in_band_count / total_count) if total_count else 0.0
    return CandidateMetrics(
        precision=precision,
        recall=recall,
        escalation_rate=escalation_rate,
        latency_score=1.0 - escalation_rate,
    )


# --- search loop ------------------------------------------------------------------------


@dataclass
class Candidate:
    lower: float
    upper: float
    metrics: CandidateMetrics
    objective: float


def _objective(metrics: CandidateMetrics, *, weights: dict[str, float]) -> float:
    return (
        weights["precision"] * metrics.precision
        + weights["recall"] * metrics.recall
        + weights["latency"] * metrics.latency_score
        - weights["cost"] * metrics.escalation_rate
    )


def _sample_candidate(rng: random.Random) -> tuple[float, float]:
    """Sample a (lower, upper) pair with lower < upper. Bounds 0..100 (score range)."""
    lo = rng.uniform(0.0, 80.0)
    up = rng.uniform(lo + 5.0, 100.0)
    return round(lo, 2), round(up, 2)


def _run_search(
    *,
    cases: list[FixtureCase],
    iterations: int,
    weights: dict[str, float],
    seed: int,
) -> list[Candidate]:
    rng = random.Random(seed)
    # always include current shipped defaults as the baseline candidate so the report
    # shows whether the recommendation actually improves over the status quo.
    initial = [(LLM_TIER_MNPI_LOWER, LLM_TIER_MNPI_UPPER)]
    samples = initial + [_sample_candidate(rng) for _ in range(iterations - 1)]
    candidates: list[Candidate] = []
    for lo, up in samples:
        metrics = _evaluate_candidate(lower=lo, upper=up, cases=cases)
        candidates.append(Candidate(
            lower=lo,
            upper=up,
            metrics=metrics,
            objective=_objective(metrics, weights=weights),
        ))
    candidates.sort(key=lambda c: c.objective, reverse=True)
    return candidates


# --- output -----------------------------------------------------------------------------


def _format_candidate(c: Candidate) -> dict[str, Any]:
    return {
        "lower": c.lower,
        "upper": c.upper,
        "objective": round(c.objective, 4),
        "metrics": {
            "precision": round(c.metrics.precision, 4),
            "recall": round(c.metrics.recall, 4),
            "escalation_rate": round(c.metrics.escalation_rate, 4),
            "latency_score": round(c.metrics.latency_score, 4),
        },
    }


def _write_apply(output_path: Path, best: Candidate, weights: dict[str, float]) -> None:
    """Write recommended bounds to a separate TOML so customer overrides remain explicit.
    The engine still uses compile-time defaults unless junas.configs.runtime opts in to
    reading this file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    body_lines = [
        '# Auto-generated by scripts/calibrate_escalation_threshold.py',
        f'# at {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}',
        '# Engine defaults remain the source of truth; junas.configs.runtime reads this',
        '# file only when CALIBRATED_BOUNDS_FILE is wired through.',
        '',
        '[llm_tier]',
        f'mnpi_lower = {best.lower}',
        f'mnpi_upper = {best.upper}',
        '',
        '[calibration]',
        f'precision = {best.metrics.precision:.4f}',
        f'recall = {best.metrics.recall:.4f}',
        f'escalation_rate = {best.metrics.escalation_rate:.4f}',
        f'objective = {best.objective:.4f}',
        '',
        '[weights]',
        *(f'{k} = {v}' for k, v in sorted(weights.items())),
        '',
    ]
    output_path.write_text("\n".join(body_lines), encoding="utf-8")


# --- CLI --------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate LLM-tier escalation thresholds")
    parser.add_argument(
        "--corpus", type=Path, default=DEFAULT_CORPUS,
        help="path to corpus dir (default: test/fixtures/legal-corpus-adversarial)",
    )
    parser.add_argument("--iterations", type=int, default=50, help="random samples to evaluate")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--w-precision", type=float, default=1.0)
    parser.add_argument("--w-recall", type=float, default=1.0)
    parser.add_argument("--w-latency", type=float, default=0.5)
    parser.add_argument("--w-cost", type=float, default=0.3)
    parser.add_argument(
        "--apply", action="store_true",
        help="write recommended bounds to config/runtime_calibrated.toml",
    )
    parser.add_argument("--top-k", type=int, default=3, help="show top-k candidates in report")
    args = parser.parse_args(argv)

    corpus_dir = args.corpus if args.corpus.is_absolute() else (REPO_ROOT / args.corpus).resolve()
    cases = _load_fixtures(corpus_dir)
    if not cases:
        print(f"no .txt fixtures found in {corpus_dir}", file=sys.stderr)
        return 1

    weights = {
        "precision": args.w_precision,
        "recall": args.w_recall,
        "latency": args.w_latency,
        "cost": args.w_cost,
    }

    print(f"calibrating against {len(cases)} fixtures in {corpus_dir.name}", file=sys.stderr)
    print(f"weights: {weights}", file=sys.stderr)
    candidates = _run_search(
        cases=cases,
        iterations=args.iterations,
        weights=weights,
        seed=args.seed,
    )

    report = {
        "corpus": str(corpus_dir.relative_to(REPO_ROOT)),
        "fixtures": len(cases),
        "iterations": args.iterations,
        "weights": weights,
        "shipped_defaults": {
            "lower": LLM_TIER_MNPI_LOWER,
            "upper": LLM_TIER_MNPI_UPPER,
        },
        "recommended": _format_candidate(candidates[0]),
        "top_k": [_format_candidate(c) for c in candidates[: args.top_k]],
    }
    print(json.dumps(report, indent=2))

    if args.apply:
        _write_apply(DEFAULT_OUTPUT, candidates[0], weights)
        print(f"wrote calibrated bounds to {DEFAULT_OUTPUT.relative_to(REPO_ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

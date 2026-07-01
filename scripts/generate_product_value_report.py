#!/usr/bin/env python3
"""Generate privacy-safe product value JSON from Prometheus text metrics."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from prometheus_client.parser import text_string_to_metric_families

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "product-value-report.json"
REWRITE_ACTIONS = frozenset({"safe_rewrite", "redact_pii", "pseudonymize", "redact", "hold_until_public"})
OVERRIDE_TAXONOMIES = frozenset({"false_positive", "policy_exception"})
OVERRIDE_ACTIONS = frozenset({"reject", "policy_exception", "accept_risk"})


def _metric_samples(metrics_text: str):
    for family in text_string_to_metric_families(metrics_text):
        for sample in family.samples:
            if sample.name.endswith("_created"):
                continue
            yield sample.name, {str(k): str(v) for k, v in sample.labels.items()}, float(sample.value)


def _number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else round(value, 4)


def _counter_dict(counter: Counter[str]) -> dict[str, int | float]:
    return {key: _number(counter[key]) for key in sorted(counter)}


def _rate(numerator: float, denominator: float, *, source: str, denominator_confidence: str) -> dict[str, Any]:
    return {
        "numerator": _number(numerator),
        "denominator": _number(denominator),
        "value": round(numerator / denominator, 4) if denominator > 0 else None,
        "source": source,
        "denominator_confidence": denominator_confidence,
    }


def build_report(metrics_text: str) -> dict[str, Any]:
    reviewed_by_surface: Counter[str] = Counter()
    review_decisions: Counter[str] = Counter()
    review_workflows: dict[str, Counter[str]] = defaultdict(Counter)
    review_surface_decisions: dict[str, Counter[str]] = defaultdict(Counter)
    policy_decisions: Counter[str] = Counter()
    required_actions: Counter[str] = Counter()
    approval_requests_total = 0.0
    approval_completed_total = 0.0
    safe_rewrite_applied_total = 0.0
    reviewer_decisions_total = 0.0
    override_decisions_total = 0.0
    observed_metrics: set[str] = set()

    for name, labels, value in _metric_samples(metrics_text):
        observed_metrics.add(name)
        if name == "junas_review_surface_total":
            surface = labels.get("surface") or "unknown"
            workflow = labels.get("workflow") or "unknown"
            decision = labels.get("decision") or "unknown"
            reviewed_by_surface[surface] += value
            review_workflows[surface][workflow] += value
            review_surface_decisions[surface][decision] += value
            review_decisions[decision] += value
        elif name == "junas_policy_decisions_total":
            policy_decisions[labels.get("decision") or "unknown"] += value
        elif name == "junas_policy_required_actions_total":
            required_actions[labels.get("action") or "unknown"] += value
        elif name == "junas_approval_requests_total":
            approval_requests_total += value
        elif name == "junas_approval_completed_total":
            approval_completed_total += value
        elif name == "junas_safe_rewrite_applied_total":
            safe_rewrite_applied_total += value
        elif name == "junas_reviewer_decisions_total":
            reviewer_decisions_total += value
            taxonomy = labels.get("decision_taxonomy") or "none"
            action = labels.get("action") or "unknown"
            if taxonomy in OVERRIDE_TAXONOMIES or action in OVERRIDE_ACTIONS:
                override_decisions_total += value

    reviewed_total = sum(reviewed_by_surface.values())
    decision_counts = policy_decisions if policy_decisions else review_decisions
    decision_source = "junas_policy_decisions_total" if policy_decisions else "junas_review_surface_total"
    decision_confidence = "complete" if policy_decisions else "partial"
    decision_total = sum(decision_counts.values())
    rewrite_required_total = sum(required_actions[action] for action in REWRITE_ACTIONS)
    approval_denominator = reviewed_total or decision_total

    missing_metrics = sorted(
        metric
        for metric in (
            "junas_review_surface_total",
            "junas_policy_decisions_total",
            "junas_policy_required_actions_total",
            "junas_approval_requests_total",
            "junas_reviewer_decisions_total",
        )
        if metric not in observed_metrics
    )

    return {
        "schema_version": "junas.product_value_report.v1",
        "generated_at_unix": int(time.time()),
        "source": {
            "type": "prometheus_text",
            "raw_content": "omitted",
            "safe_dimensions": ["surface", "workflow", "decision", "required_action", "reviewer_action"],
        },
        "summary": {
            "reviewed_documents_total": _number(reviewed_total),
            "reviewed_documents_by_surface": _counter_dict(reviewed_by_surface),
            "decision_counts": _counter_dict(decision_counts),
            "required_action_counts": _counter_dict(required_actions),
            "approval_requests_total": _number(approval_requests_total),
            "approval_completed_total": _number(approval_completed_total),
            "safe_rewrite_replacements_total": _number(safe_rewrite_applied_total),
            "reviewer_decisions_total": _number(reviewer_decisions_total),
            "override_decisions_total": _number(override_decisions_total),
        },
        "rates": {
            "block_rate": _rate(
                decision_counts["block"],
                decision_total,
                source=decision_source,
                denominator_confidence=decision_confidence,
            ),
            "warn_rate": _rate(
                decision_counts["warn"],
                decision_total,
                source=decision_source,
                denominator_confidence=decision_confidence,
            ),
            "rewrite_rate": _rate(
                rewrite_required_total,
                decision_total,
                source="junas_policy_required_actions_total / decision events",
                denominator_confidence="complete" if required_actions and decision_total else "unknown",
            ),
            "approval_rate": _rate(
                approval_requests_total,
                approval_denominator,
                source="junas_approval_requests_total / review events",
                denominator_confidence="complete" if approval_denominator else "unknown",
            ),
            "override_rate": _rate(
                override_decisions_total,
                reviewer_decisions_total,
                source="junas_reviewer_decisions_total",
                denominator_confidence="complete" if reviewer_decisions_total else "unknown",
            ),
        },
        "by_surface": [
            {
                "surface": surface,
                "reviewed_documents": _number(reviewed_by_surface[surface]),
                "decision_counts": _counter_dict(review_surface_decisions[surface]),
                "workflows": _counter_dict(review_workflows[surface]),
            }
            for surface in sorted(reviewed_by_surface)
        ],
        "missing_metrics": missing_metrics,
        "note": (
            "Report uses Prometheus counters and bounded labels only; raw text, matched spans, prompts, "
            "filenames, recipients, and reviewer rationale are not read or emitted."
        ),
    }


def _read_metrics(path: Path | None) -> str:
    if path is None or str(path) == "-":
        return sys.stdin.read()
    metrics_path = path if path.is_absolute() else REPO_ROOT / path
    return metrics_path.read_text(encoding="utf-8")


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate privacy-safe product value report JSON")
    parser.add_argument("--metrics", type=Path, default=None, help="Prometheus text file, or stdin when omitted")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    report = build_report(_read_metrics(args.metrics))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {_relative(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

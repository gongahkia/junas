#!/usr/bin/env python3
"""Offline prospective costs using configured ceilings and the completed development job."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.model_corpus import plan, validate_config, write_new  # noqa: E402


def review() -> dict:
    previous_accounted = Decimal("7.19666825")
    prior_smoke_accounted = Decimal("0.9219475")
    per_document = previous_accounted / 200
    proposals = []
    for name in ("coverage", "holdout"):
        config = validate_config(json.loads((ROOT / f"config/model_corpus.{name}.json").read_text()))
        estimate = per_document * config["documents"]
        proposals.append(
            {
                "name": name,
                "config": f"config/model_corpus.{name}.json",
                "plan": plan(config),
                "empirical_estimate_usd": str(estimate),
                "two_times_empirical_scenario_usd": str(2 * estimate),
                "proposed_cap_usd": config["spending_limit"]["provider_cap_usd"],
            }
        )
    cap = sum((Decimal(p["proposed_cap_usd"]) for p in proposals), Decimal(0))
    reserve = Decimal("8.2")
    fx, multiplier = Decimal("1.5"), Decimal("1.2")
    return {
        "schema_version": "junas.reliability_cost_review.v1",
        "paid_calls_made": 0,
        "live_calls_authorized": False,
        "proposals": proposals,
        "empirical_estimate_total_usd": str(sum(Decimal(p["empirical_estimate_usd"]) for p in proposals)),
        "proposed_combined_additional_cap_usd": str(cap),
        "previous_accounted_or_reserved_usd": str(previous_accounted + prior_smoke_accounted),
        "rounded_prior_reserve_usd": str(reserve),
        "sgd_per_usd_ceiling": str(fx),
        "fee_multiplier": str(multiplier),
        "aggregate_prior_plus_proposed_sgd_scenario": str((reserve + cap) * fx * multiplier),
        "sgd_allowance": "50",
        "within_allowance_scenario": (reserve + cap) * fx * multiplier <= 50,
        "pricing_sources": [
            "https://developers.openai.com/api/docs/models/gpt-6.2-sol",
            "https://developers.openai.com/api/docs/models/gpt-6.1-terra",
        ],
        "pricing_checked_on": "2026-11-22",
        "limitations": [
            "Empirical scaling is an estimate, not a maximum or invoice.",
            "New prompts, retries and quota rejection may increase cost.",
            "Hard caps may stop before quadrant/entity coverage is complete.",
            "SGD scenario assumes stated FX and fees; actual invoice/credits remain unverified.",
            "Refresh the holdout exclusion registry after the new development batch.",
            "No new paid authorization has been created.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_new(args.output, review())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

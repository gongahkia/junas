#!/usr/bin/env python3
"""Run candidate evaluation plus ideal-miss attribution reports."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import bucket_candidate_misses, evaluate_candidate_corpus, miss_concentration  # noqa: E402

DEFAULT_CORPUS = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "layer-attribution"
AUDIT_GRADE_ENV_KEYS = (
    "KAYPOH_LLM_ENABLED",
    "KAYPOH_LLM_PROVIDER",
    "KAYPOH_LLM_API_KEY",
    "KAYPOH_LLM_BASE_URL",
    "KAYPOH_LLM_AZURE_API_VERSION",
    "KAYPOH_LLM_TENANT_OPT_IN_OPENAI",
    "KAYPOH_LLM_TENANT_OPT_IN_AZURE_OPENAI",
)
DEFAULT_INPUT_USD_PER_M = 0.75
DEFAULT_OUTPUT_USD_PER_M = 4.50
DEFAULT_OUTPUT_TOKENS_PER_DOC = 500


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _candidate_payload(corpus: Path, *, review_profile: str) -> dict[str, Any]:
    paths = sorted(corpus.glob("**/*.txt"))
    if not paths:
        raise FileNotFoundError(f"no candidate fixtures found in {corpus}")
    reports = [
        evaluate_candidate_corpus._evaluate_one(path, review_profile=review_profile)
        for path in paths
    ]
    return {
        "generated_at_unix": int(time.time()),
        "corpus": str(corpus),
        "review_profile": review_profile,
        "summary": evaluate_candidate_corpus._summary(reports),
        "documents": [report.__dict__ for report in reports],
        "note": "candidate report only; do not update recall locks without human review.",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_attribution(
    *,
    corpus: Path,
    output_dir: Path,
    profiles: list[str],
    examples_per_cell: int = 3,
    fail_on_missed: bool = False,
    run_id: str | None = None,
) -> tuple[dict[str, Any], int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    manifest: dict[str, Any] = {
        "generated_at_unix": int(time.time()),
        "run_id": run_id,
        "corpus": str(corpus),
        "profiles": {},
        "note": (
            "Layer-attribution substrate only. Strict is deterministic/free; "
            "audit_grade may trigger configured LLM or retrieval calls."
        ),
    }
    rc = 0
    for profile in profiles:
        candidate_payload = _candidate_payload(corpus, review_profile=profile)
        bucket_payload = bucket_candidate_misses.bucket_report(candidate_payload)
        concentration_payload = miss_concentration.concentration_report(
            bucket_payload,
            examples_per_cell=examples_per_cell,
        )
        candidate_path = output_dir / f"{run_id}_{profile}_candidate_eval.json"
        bucket_path = output_dir / f"{run_id}_{profile}_miss_buckets.json"
        concentration_path = output_dir / f"{run_id}_{profile}_miss_concentration.json"
        _write_json(candidate_path, candidate_payload)
        _write_json(bucket_path, bucket_payload)
        _write_json(concentration_path, concentration_payload)
        manifest["profiles"][profile] = {
            "candidate_report": str(candidate_path),
            "bucket_report": str(bucket_path),
            "concentration_report": str(concentration_path),
            "candidate_summary": candidate_payload["summary"],
            "bucket_summary": bucket_payload["summary"],
            "concentration_summary": concentration_payload["summary"],
        }
        bad = (
            candidate_payload["summary"]["missed"]
            or candidate_payload["summary"]["must_not_detect_violations"]
        )
        if fail_on_missed and bad:
            rc = 1
    manifest_path = output_dir / f"{run_id}_manifest.json"
    manifest["manifest_report"] = str(manifest_path)
    _write_json(manifest_path, manifest)
    return manifest, rc


def _profiles_from_args(args: argparse.Namespace) -> list[str]:
    profiles = list(args.profile or ["strict"])
    if args.include_audit_grade and "audit_grade" not in profiles:
        profiles.append("audit_grade")
    return list(dict.fromkeys(profiles))


def audit_grade_preflight(*, allow_external_cost: bool) -> dict[str, Any]:
    env_state = {key: bool(os.environ.get(key, "").strip()) for key in AUDIT_GRADE_ENV_KEYS}
    provider = os.environ.get("KAYPOH_LLM_PROVIDER", "").strip() or "configured-default"
    return {
        "profile": "audit_grade",
        "allow_external_cost": allow_external_cost,
        "provider": provider,
        "env_present": env_state,
        "ready_to_run_paid_sweep": bool(allow_external_cost and env_state["KAYPOH_LLM_API_KEY"]),
        "note": (
            "No candidate evaluation was run. Re-run with --profile audit_grade --allow-external-cost "
            "only after API spend is approved."
        ),
    }


def audit_grade_cost_estimate(
    *,
    corpus: Path,
    input_usd_per_m: float = DEFAULT_INPUT_USD_PER_M,
    output_usd_per_m: float = DEFAULT_OUTPUT_USD_PER_M,
    output_tokens_per_doc: int = DEFAULT_OUTPUT_TOKENS_PER_DOC,
) -> dict[str, Any]:
    from kaypoh.review.engine import LLM_TIER_MNPI_LOWER, LLM_TIER_MNPI_UPPER, PreSendReviewEngine

    engine = PreSendReviewEngine()
    docs = 0
    band_docs = 0
    input_tokens = 0
    for path in sorted(corpus.glob("**/*.txt")):
        text, labels = evaluate_candidate_corpus._load_pair(path)
        docs += 1
        result = engine.review(
            text=text,
            source_jurisdiction=labels.get("source_jurisdiction", "SG"),
            destination_jurisdiction=labels.get("destination_jurisdiction", "SG"),
            entity_id=None,
            include_suggestions=False,
            document_type=labels.get("document_type", "generic"),
            review_profile="strict",
        )
        if LLM_TIER_MNPI_LOWER <= result.mnpi_score < LLM_TIER_MNPI_UPPER:
            band_docs += 1
            input_tokens += max(1, len(text) // 4) + 1500
    output_tokens = band_docs * max(0, output_tokens_per_doc)
    estimated_cost = (input_tokens / 1_000_000 * input_usd_per_m) + (
        output_tokens / 1_000_000 * output_usd_per_m
    )
    return {
        "docs": docs,
        "audit_grade_band_docs": band_docs,
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "input_usd_per_m": input_usd_per_m,
        "output_usd_per_m": output_usd_per_m,
        "estimated_cost_usd": round(estimated_cost, 4),
        "note": "Estimate only; provider billing is authoritative.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run candidate corpus evaluation and ideal-miss attribution reports",
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--profile", choices=("strict", "audit_grade"), action="append")
    parser.add_argument("--include-audit-grade", action="store_true")
    parser.add_argument(
        "--allow-external-cost",
        action="store_true",
        help="Required for audit_grade runs because configured helpers may spend API credits",
    )
    parser.add_argument("--examples-per-cell", type=int, default=3)
    parser.add_argument("--fail-on-missed", action="store_true")
    parser.add_argument("--run-id", help="Stable output prefix, useful for CI/tests")
    parser.add_argument("--audit-grade-cost-cap-usd", type=float)
    parser.add_argument("--audit-grade-input-usd-per-m", type=float, default=DEFAULT_INPUT_USD_PER_M)
    parser.add_argument("--audit-grade-output-usd-per-m", type=float, default=DEFAULT_OUTPUT_USD_PER_M)
    parser.add_argument(
        "--audit-grade-output-tokens-per-doc",
        type=int,
        default=DEFAULT_OUTPUT_TOKENS_PER_DOC,
    )
    parser.add_argument(
        "--audit-grade-preflight",
        action="store_true",
        help="print no-spend audit_grade readiness JSON",
    )
    args = parser.parse_args(argv)

    if args.audit_grade_preflight:
        print(
            json.dumps(
                audit_grade_preflight(allow_external_cost=args.allow_external_cost),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    profiles = _profiles_from_args(args)
    if "audit_grade" in profiles and not args.allow_external_cost:
        print(
            "audit_grade may trigger configured LLM/retrieval calls; "
            "re-run with --allow-external-cost after approving cost.",
            file=sys.stderr,
        )
        return 2

    corpus = _resolve(args.corpus)
    output_dir = _resolve(args.output_dir)
    if "audit_grade" in profiles and args.audit_grade_cost_cap_usd is not None:
        estimate = audit_grade_cost_estimate(
            corpus=corpus,
            input_usd_per_m=args.audit_grade_input_usd_per_m,
            output_usd_per_m=args.audit_grade_output_usd_per_m,
            output_tokens_per_doc=args.audit_grade_output_tokens_per_doc,
        )
        if estimate["estimated_cost_usd"] > args.audit_grade_cost_cap_usd:
            print(
                json.dumps(
                    {"cost_cap_exceeded": True, "estimate": estimate},
                    indent=2,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
    try:
        manifest, rc = run_attribution(
            corpus=corpus,
            output_dir=output_dir,
            profiles=profiles,
            examples_per_cell=max(0, args.examples_per_cell),
            fail_on_missed=args.fail_on_missed,
            run_id=args.run_id,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"wrote {manifest['manifest_report']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

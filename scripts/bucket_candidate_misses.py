#!/usr/bin/env python3
"""Bucket ideal-tier candidate misses into roadmap-actionable reasons."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

BUCKETS = frozenset({
    "conjunction_miss",
    "singling_out_miss",
    "true_inference_miss",
    "coverage_gap",
    "needs_review",
})

PSEUDONYMIZED_LINKABLE = frozenset({
    "employee_id",
    "customer_account_number",
    "medical_record_number",
    "internal_session_id",
    "bank_customer_reference",
    "insurance_member_id",
})
SPECIAL_CATEGORY = frozenset({
    "religious_belief",
    "trade_union_membership",
    "political_opinion",
    "health_condition",
    "medical_treatment",
    "biometric_identifier",
    "genetic_data",
    "sexual_orientation",
    "sex_life_reference",
})
PRIVACY_EVENT = frozenset({
    "cross_border_transfer_marker",
    "consent_withdrawal_marker",
    "data_minimisation_marker",
    "minor_data_reference",
})
ONLINE_DEVICE = frozenset({
    "date_of_birth",
    "age_reference",
    "ip_address",
    "mac_address",
    "imei",
    "cookie_id",
    "advertising_id",
    "device_serial_number",
})
UNIVERSAL_DIRECT = frozenset({
    "named_person",
    "email_address",
    "phone_number",
    "passport_number",
    "bank_account",
})
LOCAL_IDENTIFIER_PREFIXES = (
    "sg_",
    "my_",
    "id_",
    "th_",
    "ph_",
    "vn_",
    "hk_",
    "au_",
    "jp_",
    "kr_",
    "in_",
    "cn_",
    "ae_",
    "sa_",
    "us_",
    "uk_",
    "eu_",
)
MNPI_LEXICON = frozenset({
    "material_event",
    "nonpublic_marker",
    "transaction_codename",
    "definitive_agreement",
    "material_adverse_change",
    "embargo_marker",
    "financial_amount",
    "financial_percentage",
    "large_number",
})
MNPI_CONTEXT = frozenset({
    "contingent_mnpi_language",
    "tipping_language",
    "selective_disclosure_risk",
    "insider_list_marker",
    "information_barrier_marker",
    "blackout_period_reference",
})
SECTOR_MNPI = frozenset({
    "dpt_pre_listing_marker",
    "dpt_protocol_event_marker",
    "esg_climate_pre_disclosure",
    "esg_target_revision",
    "cyber_incident_pre_disclosure",
})


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def detector_family(rule: str) -> str:
    if rule == "quasi_identifier_combination":
        return "quasi_identifier"
    if rule in PSEUDONYMIZED_LINKABLE:
        return "pseudonymised_linkable"
    if rule in SPECIAL_CATEGORY:
        return "special_category"
    if rule in PRIVACY_EVENT:
        return "privacy_event"
    if rule in ONLINE_DEVICE:
        return "online_device"
    if rule in UNIVERSAL_DIRECT or rule.startswith(LOCAL_IDENTIFIER_PREFIXES):
        return "direct_identifier"
    if rule in MNPI_LEXICON:
        return "mnpi_lexicon"
    if rule in MNPI_CONTEXT:
        return "mnpi_context"
    if rule in SECTOR_MNPI:
        return "sector_mnpi"
    return "unknown"


def bucket_for(miss: dict[str, Any]) -> tuple[str, str]:
    rule = str(miss.get("rule") or "")
    family = detector_family(rule)
    notes = " ".join(
        str(miss.get(key) or "").casefold()
        for key in ("concept", "reason", "matched_text")
    )
    if rule == "quasi_identifier_combination":
        return "singling_out_miss", "quasi-identifier miss belongs to Layer-2 singling-out"
    if any(token in notes for token in (
        "cross-document",
        "domain inference",
        "legal judgement",
        "legal judgment",
        "public-status",
        "public status",
        "not generally known",
        "sector-specific materiality",
    )):
        return "true_inference_miss", "label rationale requires domain/public-status inference"
    if family in {
        "direct_identifier",
        "pseudonymised_linkable",
        "special_category",
        "privacy_event",
        "online_device",
        "mnpi_lexicon",
        "sector_mnpi",
    }:
        return "coverage_gap", f"{family} detector did not cover the ideal span"
    if family == "mnpi_context":
        return "conjunction_miss", "contextual MNPI marker likely belongs to Layer-2 element scoring"
    return "needs_review", "no deterministic bucket heuristic matched; manual review required"


def bucket_report(eval_report: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    summary_by_bucket: Counter[str] = Counter()
    summary_by_jurisdiction: dict[str, Counter[str]] = defaultdict(Counter)
    summary_by_family: dict[str, Counter[str]] = defaultdict(Counter)
    summary_by_rule: dict[str, Counter[str]] = defaultdict(Counter)

    for doc in eval_report.get("documents", []):
        jurisdiction = str(doc.get("source_jurisdiction") or "")
        for miss in doc.get("ideal_missed", []):
            rule = str(miss.get("rule") or "")
            family = detector_family(rule)
            bucket, rationale = bucket_for(miss)
            entry = {
                "doc_id": str(doc.get("doc_id") or ""),
                "path": str(doc.get("path") or ""),
                "source_jurisdiction": jurisdiction,
                "destination_jurisdiction": str(doc.get("destination_jurisdiction") or ""),
                "document_type": str(doc.get("document_type") or ""),
                "rule": rule,
                "category": str(miss.get("category") or ""),
                "matched_text": str(miss.get("matched_text") or ""),
                "concept": str(miss.get("concept") or ""),
                "label_reason": str(miss.get("reason") or ""),
                "bucket": bucket,
                "detector_family": family,
                "bucket_reason": rationale,
                "review_status": "heuristic_needs_spot_check" if bucket != "needs_review" else "needs_review",
            }
            entries.append(entry)
            summary_by_bucket[bucket] += 1
            summary_by_jurisdiction[jurisdiction][bucket] += 1
            summary_by_family[family][bucket] += 1
            summary_by_rule[rule][bucket] += 1

    return {
        "generated_at_unix": int(time.time()),
        "source_eval_report": eval_report.get("corpus", ""),
        "source_review_profile": eval_report.get("review_profile", "unknown"),
        "bucket_schema": sorted(BUCKETS),
        "summary": {
            "miss_count": len(entries),
            "by_bucket": dict(sorted(summary_by_bucket.items())),
            "by_jurisdiction": {
                key: dict(sorted(value.items())) for key, value in sorted(summary_by_jurisdiction.items())
            },
            "by_detector_family": {
                key: dict(sorted(value.items())) for key, value in sorted(summary_by_family.items())
            },
            "by_rule": {
                key: dict(sorted(value.items())) for key, value in sorted(summary_by_rule.items())
            },
        },
        "misses": entries,
        "note": "heuristic item-124 bucketing; spot-check before treating buckets as reviewed truth.",
    }


def _write_sidecars(payload: dict[str, Any]) -> int:
    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in payload["misses"]:
        by_path[entry["path"]].append(entry)
    written = 0
    for path_text, entries in by_path.items():
        fixture_path = REPO_ROOT / path_text
        if not fixture_path.exists():
            continue
        sidecar = fixture_path.with_suffix(".bucket.json")
        body = {
            "doc_id": entries[0]["doc_id"],
            "path": path_text,
            "review_status": "heuristic_needs_spot_check",
            "miss_buckets": entries,
            "note": payload["note"],
        }
        sidecar.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bucket candidate ideal misses into roadmap-actionable reasons")
    parser.add_argument("--eval-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Write bucket report JSON")
    parser.add_argument("--write-sidecars", action="store_true", help="Write adjacent .bucket.json sidecars")
    args = parser.parse_args(argv)

    eval_report_path = args.eval_report if args.eval_report.is_absolute() else REPO_ROOT / args.eval_report
    if not eval_report_path.exists():
        print(f"eval report missing: {eval_report_path}", file=sys.stderr)
        return 2
    payload = bucket_report(_read_json(eval_report_path))
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"wrote {output}")
    else:
        print(rendered, end="")
    if args.write_sidecars:
        print(f"wrote sidecars={_write_sidecars(payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

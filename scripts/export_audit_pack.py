#!/usr/bin/env python3
"""Export a tamper-evident audit pack for a single review session.

The pack is a ZIP with:
    manifest.json    -- review_id, text_hash, doc metadata, decision summary, pack_hmac
    journal.jsonl    -- the slice of journal entries for this review session
    findings.json    -- findings from the review_started event
    decisions.json   -- one entry per decision_recorded event
    privacy_ledger.json (if present) -- empty placeholder; future hook for outbound calls

The export is itself recorded as an `audit_exported` event in the journal so the chain
captures it. `pack_hmac` is HMAC-SHA256(JUNAS_JOURNAL_KEY, canonical-manifest-without-hmac).

Usage:
    python3 scripts/export_audit_pack.py <review_id>
    python3 scripts/export_audit_pack.py <review_id> --output ./out/audit.zip
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from junas.review import jurisdictions  # noqa: E402
from junas.review.decisions import (  # noqa: E402
    ALLOWED_ACTIONS,
    DECISION_ACTIONS,
    EVENT_ANONYMIZE_APPLIED,
    EVENT_AUDIT_EXPORTED,
    EVENT_DECISION_RECORDED,
    EVENT_REVIEW_STARTED,
)
from junas.review.journal import (  # noqa: E402
    JournalEntry,
    _journal_key,
    append_event,
    read_journal,
    verify_chain,
)


def _canonicalize_manifest(manifest: dict) -> bytes:
    clone = dict(manifest)
    clone.pop("pack_hmac", None)
    return json.dumps(clone, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _seal_manifest(manifest: dict) -> str:
    return hmac.new(_journal_key(), _canonicalize_manifest(manifest), hashlib.sha256).hexdigest()


def _entries_to_dicts(entries: list[JournalEntry]) -> list[dict]:
    return [json.loads(entry.to_json()) for entry in entries]


def _parse_iso(ts: str) -> float:
    # journal timestamps are %Y-%m-%dT%H:%M:%SZ; treat as UTC epoch seconds.
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def _build_reviewer_rollup(decisions: list[dict]) -> dict[str, dict[str, int]]:
    """Per-reviewer action counts. Surfaces maker-checker violations: when one reviewer's
    counts dominate accept-only decisions, an auditor can spot self-approval at a glance."""
    rollup: dict[str, dict[str, int]] = defaultdict(lambda: {action: 0 for action in DECISION_ACTIONS})
    for decision in decisions:
        reviewer = decision.get("reviewer_id") or "unattributed"
        action = decision.get("action")
        if action in ALLOWED_ACTIONS:
            rollup[reviewer][action] += 1
    return {k: dict(v) for k, v in rollup.items()}


def _build_action_rates_by_rule(findings: list[dict], decisions: list[dict]) -> dict[str, dict[str, float | int]]:
    finding_rule = {str(finding.get("id") or ""): str(finding.get("rule") or "unknown") for finding in findings}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {**{action: 0 for action in DECISION_ACTIONS}, "total": 0})
    for decision in decisions:
        action = str(decision.get("action") or "")
        if action not in ALLOWED_ACTIONS:
            continue
        rule = finding_rule.get(str(decision.get("finding_id") or ""), "unknown")
        counts[rule][action] += 1
        counts[rule]["total"] += 1
    rates: dict[str, dict[str, float | int]] = {}
    for rule, rule_counts in sorted(counts.items()):
        total = rule_counts["total"] or 1
        rates[rule] = {action: rule_counts[action] for action in DECISION_ACTIONS}
        rates[rule]["total"] = rule_counts["total"]
        rates[rule].update({f"{action}_rate": round(rule_counts[action] / total, 4) for action in DECISION_ACTIONS})
    return rates


def _build_privacy_operation_counters(entries: list[JournalEntry]) -> dict[str, int]:
    counters: dict[str, int] = defaultdict(int)
    for entry in entries:
        operation = str(entry.payload.get("privacy_operation") or "")
        if not operation and entry.event_type == EVENT_ANONYMIZE_APPLIED:
            operation = "anonymize_legacy"
        if operation in {"pseudonymize", "anonymize", "redact", "anonymize_legacy"}:
            counters[operation] += 1
    return {key: counters[key] for key in sorted(counters)}


def _jurisdiction_codes_for_findings(findings: list[dict], init_payload: dict) -> list[str]:
    codes: set[str] = set()
    for field in ("source_jurisdiction", "destination_jurisdiction"):
        value = str(init_payload.get(field) or "").strip().upper()
        if value:
            codes.add(jurisdictions.normalize_jurisdiction(value))
    for finding in findings:
        for part in str(finding.get("jurisdiction") or "").split("+"):
            value = part.strip().upper()
            if value:
                codes.add(jurisdictions.normalize_jurisdiction(value))
    return sorted(codes)


def _build_defensibility_manifest(
    *,
    findings: list[dict],
    init_payload: dict,
    action_rates_by_rule: dict[str, dict[str, float | int]],
) -> dict:
    report_codes = _jurisdiction_codes_for_findings(findings, init_payload)
    return {
        "artifact_scope": "internal benchmarking/procurement-support; not legal advice",
        "statutory_coverage": "statutory-coverage.md",
        "defensibility_reports": [f"defensibility/{code}.md" for code in report_codes],
        "findings": [
            {
                "finding_id": finding.get("id"),
                "category": finding.get("category"),
                "rule": finding.get("rule"),
                "jurisdiction": finding.get("jurisdiction"),
                "severity": finding.get("severity"),
                "legal_basis": finding.get("legal_basis"),
                "source_verification": finding.get("source_verification", "not_checked"),
                "metadata": finding.get("metadata", {}),
                "reviewer_action_rates_by_rule": action_rates_by_rule.get(str(finding.get("rule") or ""), {}),
            }
            for finding in findings
        ],
        "privacy_note": (
            "Manifest excludes raw reviewer rationale and does not add raw document text beyond "
            "the existing findings.json payload."
        ),
    }


def _check_min_wait(entries: list[JournalEntry]) -> tuple[bool, str | None]:
    """Optional gate: if JUNAS_AUDIT_MIN_WAIT_SECONDS is set, require the elapsed time
    between session start and the earliest decision_recorded to exceed that bound. Surfaces
    batch-approval red flags where a reviewer rubber-stamps every finding in seconds."""
    bound_raw = os.environ.get("JUNAS_AUDIT_MIN_WAIT_SECONDS", "").strip()
    if not bound_raw:
        return True, None
    try:
        bound = float(bound_raw)
    except ValueError:
        return True, None
    if bound <= 0:
        return True, None

    start_ts: float | None = None
    earliest_decision_ts: float | None = None
    for entry in entries:
        if entry.event_type == EVENT_REVIEW_STARTED and start_ts is None:
            start_ts = _parse_iso(entry.ts)
        elif entry.event_type == EVENT_DECISION_RECORDED:
            ts = _parse_iso(entry.ts)
            if earliest_decision_ts is None or ts < earliest_decision_ts:
                earliest_decision_ts = ts
    if start_ts is None or earliest_decision_ts is None:
        return True, None
    elapsed = earliest_decision_ts - start_ts
    if elapsed < bound:
        return False, (
            f"min-wait violation: first decision recorded {elapsed:.0f}s after review start; "
            f"JUNAS_AUDIT_MIN_WAIT_SECONDS={bound:g}"
        )
    return True, None


def build_pack(review_id: str, output_path: Path, *, include_defensibility: bool = False) -> dict:
    entries = read_journal(review_id=review_id)
    if not entries or entries[0].event_type != EVENT_REVIEW_STARTED:
        raise SystemExit(f"no review_started event found for {review_id}")

    valid, errors = verify_chain()
    chain_status = "valid" if valid else "tampered"

    init_payload = entries[0].payload
    decisions = [
        {**entry.payload, "seq": entry.seq, "ts": entry.ts, "hmac": entry.hmac}
        for entry in entries
        if entry.event_type == EVENT_DECISION_RECORDED
    ]
    reviewer_rollup = _build_reviewer_rollup(decisions)
    findings = list(init_payload.get("findings", []) or [])
    reviewer_action_rates_by_rule = _build_action_rates_by_rule(findings, decisions)
    privacy_operations = _build_privacy_operation_counters(entries)
    wait_ok, wait_warning = _check_min_wait(entries)
    manifest = {
        "review_id": review_id,
        "text_hash": init_payload.get("text_hash"),
        "document_type": init_payload.get("document_type"),
        "source_jurisdiction": init_payload.get("source_jurisdiction"),
        "destination_jurisdiction": init_payload.get("destination_jurisdiction"),
        "findings_total": len(findings),
        "decisions_total": len(decisions),
        "journal_chain_status": chain_status,
        "journal_chain_errors": errors,
        "first_seq": entries[0].seq,
        "last_seq": entries[-1].seq,
        "reviewer_rollup": reviewer_rollup,
        "reviewer_action_rates_by_rule": reviewer_action_rates_by_rule,
        "privacy_operations": privacy_operations,
        "defensibility_included": include_defensibility,
        "min_wait_status": "ok" if wait_ok else "violation",
        "min_wait_warning": wait_warning,
    }
    defensibility_manifest = None
    report_codes: list[str] = []
    if include_defensibility:
        defensibility_manifest = _build_defensibility_manifest(
            findings=findings,
            init_payload=init_payload,
            action_rates_by_rule=reviewer_action_rates_by_rule,
        )
        report_codes = [
            item.removeprefix("defensibility/").removesuffix(".md")
            for item in defensibility_manifest["defensibility_reports"]
        ]
    manifest["pack_hmac"] = _seal_manifest(manifest)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        archive.writestr(
            "journal.jsonl",
            "\n".join(json.dumps(e, sort_keys=True, separators=(",", ":")) for e in _entries_to_dicts(entries)) + "\n",
        )
        archive.writestr("findings.json", json.dumps(findings, indent=2))
        archive.writestr("decisions.json", json.dumps(decisions, indent=2))
        if include_defensibility and defensibility_manifest is not None:
            statutory_path = REPO_ROOT / "docs" / "statutory-coverage.md"
            archive.write(statutory_path, "statutory-coverage.md")
            archive.writestr(
                "defensibility_manifest.json",
                json.dumps(defensibility_manifest, indent=2, sort_keys=True),
            )
            for code in report_codes:
                report_path = REPO_ROOT / "docs" / "defensibility" / f"{code}.md"
                if report_path.exists():
                    archive.write(report_path, f"defensibility/{code}.md")

    append_event(
        event_type=EVENT_AUDIT_EXPORTED,
        review_id=review_id,
        payload={
            "pack_path": str(output_path),
            "pack_hmac": manifest["pack_hmac"],
            "decisions_total": manifest["decisions_total"],
            "defensibility_included": include_defensibility,
        },
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a Junas review audit pack")
    parser.add_argument("review_id", help="Review session ID (the request_id from the original /review call)")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path. Defaults to ./junas-journal/audit_pack_<review_id>.zip",
    )
    parser.add_argument(
        "--include-defensibility",
        action="store_true",
        help="Bundle statutory coverage, defensibility reports, and per-finding manifest.",
    )
    args = parser.parse_args(argv)

    if args.output is None:
        # default location lives beside the journal so audit artefacts stay grouped
        from junas.review.journal import journal_dir

        args.output = journal_dir() / f"audit_pack_{args.review_id}.zip"

    manifest = build_pack(args.review_id, args.output, include_defensibility=args.include_defensibility)
    print(f"wrote {args.output}")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if manifest["journal_chain_status"] != "valid":
        return 1
    if manifest.get("min_wait_status") == "violation":
        print(f"warning: {manifest.get('min_wait_warning')}", file=sys.stderr)
        return 2  # surface the red flag but the pack itself is still valid
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

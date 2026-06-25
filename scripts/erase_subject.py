#!/usr/bin/env python3
"""Erase persisted references for a data subject without indexing raw PII."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kaypoh.anonymize.mapping_store import load_mapping, purge_mapping  # noqa: E402
from kaypoh.review.decisions import (  # noqa: E402
    EVENT_REVIEW_STARTED,
    EVENT_SUBJECT_ERASURE_RECORDED,
    record_subject_erasure,
)
from kaypoh.review.journal import append_event, journal_dir, read_journal  # noqa: E402
from kaypoh.review.subject_index import (  # noqa: E402
    SubjectIndexError,
    index_mapping,
    index_review_findings,
    lookup_subject,
    remove_subject,
    reset_index,
)


def _mapping_dir(tenant_id: str | None) -> Path:
    return journal_dir(tenant_id) / "mappings"


def _backfill_index(*, tenant_id: str | None) -> dict[str, Any]:
    reset_index(tenant_id=tenant_id)
    indexed_mappings = 0
    indexed_review_sessions = 0

    mapping_dir = _mapping_dir(tenant_id)
    if mapping_dir.exists():
        for path in sorted(mapping_dir.glob("*.json")):
            mapping = load_mapping(path.stem, tenant_id=tenant_id)
            if not mapping:
                continue
            indexed_mappings += index_mapping(
                document_hash=path.stem,
                mapping=mapping,
                tenant_id=tenant_id,
            )

    for entry in read_journal(tenant_id=tenant_id):
        if entry.event_type != EVENT_REVIEW_STARTED:
            continue
        findings = list(entry.payload.get("findings", []) or [])
        if not findings:
            continue
        indexed_review_sessions += index_review_findings(
            review_id=entry.review_id,
            document_hash=str(entry.payload.get("text_hash", "") or ""),
            findings=findings,
            tenant_id=tenant_id,
        )

    return {
        "mode": "backfill",
        "tenant": tenant_id or "",
        "indexed_mapping_entries": indexed_mappings,
        "indexed_review_entries": indexed_review_sessions,
    }


def _review_erasure_groups(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry.get("entry_type") != "review":
            continue
        review_id = str(entry.get("review_id", "") or "subject_erasure")
        group = grouped.setdefault(
            review_id,
            {
                "review_id": review_id,
                "document_hash": str(entry.get("document_hash", "") or ""),
                "finding_ids": set(),
                "rules": set(),
            },
        )
        if entry.get("finding_id"):
            group["finding_ids"].add(str(entry["finding_id"]))
        if entry.get("rule"):
            group["rules"].add(str(entry["rule"]))
    return grouped


def _erase_subject(
    *,
    value: str,
    citation: str,
    tenant_id: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    lookup = lookup_subject(value, tenant_id=tenant_id)
    pii_hash = lookup["pii_hash"]
    entries = list(lookup.get("entries", []) or [])
    mapping_hashes = sorted(
        {
            str(entry.get("document_hash", "") or "")
            for entry in entries
            if entry.get("entry_type") == "mapping" and entry.get("document_hash")
        }
    )
    review_groups = _review_erasure_groups(entries)

    payload: dict[str, Any] = {
        "mode": "erase",
        "tenant": tenant_id or "",
        "pii_hash": pii_hash,
        "dry_run": dry_run,
        "matched_entries": len(entries),
        "matched_mapping_documents": mapping_hashes,
        "matched_review_sessions": sorted(review_groups),
        "deleted_mapping_documents": [],
        "missing_mapping_documents": [],
        "journaled_review_sessions": [],
        "removed_index_entries": 0,
    }
    if dry_run or not entries:
        return payload

    deleted_hashes: list[str] = []
    missing_hashes: list[str] = []
    for document_hash in mapping_hashes:
        if purge_mapping(document_hash, tenant_id=tenant_id):
            deleted_hashes.append(document_hash)
        else:
            missing_hashes.append(document_hash)
    payload["deleted_mapping_documents"] = deleted_hashes
    payload["missing_mapping_documents"] = missing_hashes

    if deleted_hashes or missing_hashes:
        append_event(
            event_type=EVENT_SUBJECT_ERASURE_RECORDED,
            review_id="subject_erasure",
            payload={
                "pii_hash": pii_hash,
                "citation": citation,
                "deleted_document_hashes": deleted_hashes,
                "missing_document_hashes": missing_hashes,
            },
            tenant_id=tenant_id,
        )

    for review_id, group in sorted(review_groups.items()):
        record_subject_erasure(
            review_id=review_id,
            pii_hash=pii_hash,
            citation=citation,
            document_hash=str(group.get("document_hash", "") or ""),
            finding_ids=list(group["finding_ids"]),
            rules=list(group["rules"]),
            tenant_id=tenant_id,
        )
        payload["journaled_review_sessions"].append(review_id)

    payload["removed_index_entries"] = remove_subject(value, tenant_id=tenant_id)
    return payload


def _print_text(payload: dict[str, Any]) -> None:
    if payload["mode"] == "backfill":
        print(
            "backfilled subject index: "
            f"{payload['indexed_mapping_entries']} mapping entry(s), "
            f"{payload['indexed_review_entries']} review entry(s)"
        )
        return
    action = "would erase" if payload["dry_run"] else "erased"
    print(
        f"{action} pii_hash={payload['pii_hash']} "
        f"entries={payload['matched_entries']} "
        f"mappings={len(payload['matched_mapping_documents'])} "
        f"reviews={len(payload['matched_review_sessions'])}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Erase Kaypoh subject references by HMAC-index lookup")
    parser.add_argument("--tenant", "--tenant-id", dest="tenant_id", help="tenant storage id")
    parser.add_argument("--value", help="raw subject value to hash and erase; never persisted by this script")
    parser.add_argument("--citation", default="", help="legal or ticket citation for non-dry-run erasure")
    parser.add_argument("--dry-run", action="store_true", help="show matches without deleting or journaling")
    parser.add_argument("--backfill", action="store_true", help="rebuild the reverse index from mappings and journal")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    if not args.backfill and not args.value:
        parser.error("provide --value, --backfill, or both")
    if args.value and not args.dry_run and not args.citation.strip():
        parser.error("--citation is required for non-dry-run erasure")

    payloads: list[dict[str, Any]] = []
    try:
        if args.backfill:
            payloads.append(_backfill_index(tenant_id=args.tenant_id))
        if args.value:
            payloads.append(
                _erase_subject(
                    value=args.value,
                    citation=args.citation.strip(),
                    tenant_id=args.tenant_id,
                    dry_run=bool(args.dry_run),
                )
            )
    except SubjectIndexError as exc:
        parser.exit(status=2, message=f"subject index error: {exc}\n")

    output: dict[str, Any] = payloads[0] if len(payloads) == 1 else {"operations": payloads}
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        for payload in payloads:
            _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

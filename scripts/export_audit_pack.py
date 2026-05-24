#!/usr/bin/env python3
"""Export a tamper-evident audit pack for a single review session.

The pack is a ZIP with:
    manifest.json    -- review_id, text_hash, doc metadata, decision summary, pack_hmac
    journal.jsonl    -- the slice of journal entries for this review session
    findings.json    -- findings from the review_started event
    decisions.json   -- one entry per decision_recorded event
    privacy_ledger.json (if present) -- empty placeholder; future hook for outbound calls

The export is itself recorded as an `audit_exported` event in the journal so the chain
captures it. `pack_hmac` is HMAC-SHA256(KAYPOH_JOURNAL_KEY, canonical-manifest-without-hmac).

Usage:
    python3 scripts/export_audit_pack.py <review_id>
    python3 scripts/export_audit_pack.py <review_id> --output ./out/audit.zip
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.decisions import EVENT_AUDIT_EXPORTED, EVENT_DECISION_RECORDED, EVENT_REVIEW_STARTED  # noqa: E402
from kaypoh.review.journal import (  # noqa: E402
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


def build_pack(review_id: str, output_path: Path) -> dict:
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
    manifest = {
        "review_id": review_id,
        "text_hash": init_payload.get("text_hash"),
        "document_type": init_payload.get("document_type"),
        "source_jurisdiction": init_payload.get("source_jurisdiction"),
        "destination_jurisdiction": init_payload.get("destination_jurisdiction"),
        "findings_total": len(init_payload.get("findings", [])),
        "decisions_total": len(decisions),
        "journal_chain_status": chain_status,
        "journal_chain_errors": errors,
        "first_seq": entries[0].seq,
        "last_seq": entries[-1].seq,
    }
    manifest["pack_hmac"] = _seal_manifest(manifest)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        archive.writestr(
            "journal.jsonl",
            "\n".join(json.dumps(e, sort_keys=True, separators=(",", ":")) for e in _entries_to_dicts(entries)) + "\n",
        )
        archive.writestr("findings.json", json.dumps(init_payload.get("findings", []), indent=2))
        archive.writestr("decisions.json", json.dumps(decisions, indent=2))

    append_event(
        event_type=EVENT_AUDIT_EXPORTED,
        review_id=review_id,
        payload={
            "pack_path": str(output_path),
            "pack_hmac": manifest["pack_hmac"],
            "decisions_total": manifest["decisions_total"],
        },
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a Kaypoh review audit pack")
    parser.add_argument("review_id", help="Review session ID (the request_id from the original /review call)")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path. Defaults to ./kaypoh-journal/audit_pack_<review_id>.zip",
    )
    args = parser.parse_args(argv)

    if args.output is None:
        # default location lives beside the journal so audit artefacts stay grouped
        from kaypoh.review.journal import journal_dir

        args.output = journal_dir() / f"audit_pack_{args.review_id}.zip"

    manifest = build_pack(args.review_id, args.output)
    print(f"wrote {args.output}")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["journal_chain_status"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())

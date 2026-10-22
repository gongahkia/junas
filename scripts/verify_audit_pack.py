#!/usr/bin/env python3
"""Verify an exported audit pack.

Checks:
  1. ZIP layout (manifest.json, journal.jsonl, findings.json, decisions.json)
  2. manifest pack_hmac matches recomputed HMAC over the canonical manifest
  3. every bundled member is bound to that signed manifest
  4. each review-slice entry has a valid HMAC and ordered sequence
  5. findings and decisions match the authenticated journal slice

The slice can omit other reviews. Complete-chain verification is the exporter's
signed snapshot attestation, not an independent replay of omitted records here.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# load _seal_manifest from the sibling exporter script without making scripts/ a package
import importlib.util as _import_util  # noqa: E402

from junas.review.journal import (  # noqa: E402
    GENESIS_HASH,
    JournalEntry,
    _compute_hmac,
    _resolve_key_for_version,
)

_exporter_spec = _import_util.spec_from_file_location(
    "_junas_export_audit_pack",
    str(Path(__file__).resolve().parent / "export_audit_pack.py"),
)
assert _exporter_spec is not None and _exporter_spec.loader is not None
_exporter = _import_util.module_from_spec(_exporter_spec)
_exporter_spec.loader.exec_module(_exporter)
_seal_manifest = _exporter._seal_manifest  # type: ignore[attr-defined]


def _verify_archive(pack_path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not pack_path.exists():
        return False, [f"pack not found: {pack_path}"]

    with zipfile.ZipFile(pack_path, "r") as archive:
        members = archive.infolist()
        names = set(archive.namelist())
        if len(names) != len(members):
            return False, ["duplicate archive members"]
        if len(members) > 256 or sum(member.file_size for member in members) > 64 * 1024 * 1024:
            return False, ["archive exceeds verification limits"]
        if any(
            "\\" in name or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts for name in names
        ):
            return False, ["unsafe archive member path"]
        for required in ("manifest.json", "journal.jsonl", "findings.json", "decisions.json"):
            if required not in names:
                errors.append(f"missing {required}")
        if errors:
            return False, errors

        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict):
            return False, ["invalid manifest"]
        if manifest.get("pack_schema_version") != 2:
            return False, ["legacy pack lacks signed member hashes; re-export with the current tool"]
        recomputed = _seal_manifest(manifest)
        if not hmac.compare_digest(recomputed, str(manifest.get("pack_hmac", ""))):
            errors.append("pack_hmac mismatch (manifest tampered or wrong JUNAS_JOURNAL_KEY)")
        hashes = manifest.get("members_sha256")
        if not isinstance(hashes, dict) or set(hashes) | {"manifest.json"} != names:
            return False, errors + ["archive membership does not match signed manifest"]
        for name, expected_hash in hashes.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected_hash:
                errors.append(f"member hash mismatch: {name}")
        if manifest.get("journal_scope") != "review_slice" or manifest.get("journal_chain_status") != "valid":
            errors.append("journal snapshot was not verified at export")
        if errors:
            return False, errors

        journal_lines = [line for line in archive.read("journal.jsonl").decode("utf-8").splitlines() if line.strip()]
        entries = [JournalEntry.from_dict(json.loads(line)) for line in journal_lines]
        if not entries or entries[0].event_type != _exporter.EVENT_REVIEW_STARTED:
            return False, ["missing review-start entry"]
        if manifest.get("first_seq") != entries[0].seq or manifest.get("last_seq") != entries[-1].seq:
            errors.append("journal slice bounds do not match manifest")
        previous = None
        for entry in entries:
            if entry.review_id != manifest.get("review_id") or entry.seq < 0:
                errors.append("journal slice contains another review or invalid sequence")
            if previous is not None:
                if entry.seq <= previous.seq:
                    errors.append("journal slice is not strictly ordered")
                if entry.seq == previous.seq + 1 and entry.prev_hash != previous.hmac:
                    errors.append("adjacent journal entries are not linked")
            elif entry.seq == 0 and entry.prev_hash != GENESIS_HASH:
                errors.append("invalid genesis link")
            expected = _compute_hmac(
                seq=entry.seq,
                ts=entry.ts,
                event_type=entry.event_type,
                review_id=entry.review_id,
                payload=entry.payload,
                prev_hash=entry.prev_hash,
                key_bytes=_resolve_key_for_version(entry.key_version),
            )
            if not hmac.compare_digest(expected, entry.hmac):
                errors.append(f"journal entry HMAC mismatch at sequence {entry.seq}")
            previous = entry

        findings = json.loads(archive.read("findings.json"))
        decisions = json.loads(archive.read("decisions.json"))
        if manifest.get("findings_total") != len(findings):
            errors.append(f"findings_total {manifest.get('findings_total')} != actual {len(findings)}")
        if manifest.get("decisions_total") != len(decisions):
            errors.append(f"decisions_total {manifest.get('decisions_total')} != actual {len(decisions)}")
        expected_findings = list(entries[0].payload.get("findings", []) or [])
        expected_decisions = [
            {**entry.payload, "seq": entry.seq, "ts": entry.ts, "hmac": entry.hmac}
            for entry in entries
            if entry.event_type == _exporter.EVENT_DECISION_RECORDED
        ]
        if findings != expected_findings or decisions != expected_decisions:
            errors.append("findings or decisions differ from the authenticated journal slice")

    return not errors, errors


def verify_pack(pack_path: Path) -> tuple[bool, list[str]]:
    try:
        return _verify_archive(pack_path)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, zipfile.BadZipFile):
        return False, ["malformed or unreadable audit pack, or unavailable verification key"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a Junas audit pack")
    parser.add_argument("pack", type=Path, help="Path to the audit_pack_*.zip")
    args = parser.parse_args(argv)

    valid, errors = verify_pack(args.pack)
    print(f"pack: {args.pack}")
    print(f"status: {'valid' if valid else 'INVALID'}")
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

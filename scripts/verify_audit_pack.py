#!/usr/bin/env python3
"""Verify an exported audit pack.

Checks:
  1. ZIP layout (manifest.json, journal.jsonl, findings.json, decisions.json)
  2. manifest pack_hmac matches recomputed HMAC over the canonical manifest
  3. journal.jsonl HMAC chain is internally consistent
  4. findings_total / decisions_total match the bundled payloads
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.journal import JournalEntry, verify_chain  # noqa: E402

# load _seal_manifest from the sibling exporter script without making scripts/ a package
import importlib.util as _import_util  # noqa: E402

_exporter_spec = _import_util.spec_from_file_location(
    "_kaypoh_export_audit_pack",
    str(Path(__file__).resolve().parent / "export_audit_pack.py"),
)
assert _exporter_spec is not None and _exporter_spec.loader is not None
_exporter = _import_util.module_from_spec(_exporter_spec)
_exporter_spec.loader.exec_module(_exporter)
_seal_manifest = _exporter._seal_manifest  # type: ignore[attr-defined]


def verify_pack(pack_path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not pack_path.exists():
        return False, [f"pack not found: {pack_path}"]

    with zipfile.ZipFile(pack_path, "r") as archive:
        names = set(archive.namelist())
        for required in ("manifest.json", "journal.jsonl", "findings.json", "decisions.json"):
            if required not in names:
                errors.append(f"missing {required}")
        if errors:
            return False, errors

        manifest = json.loads(archive.read("manifest.json"))
        recomputed = _seal_manifest(manifest)
        if recomputed != manifest.get("pack_hmac"):
            errors.append("pack_hmac mismatch (manifest tampered or wrong KAYPOH_JOURNAL_KEY)")

        journal_lines = [line for line in archive.read("journal.jsonl").decode("utf-8").splitlines() if line.strip()]
        entries = [JournalEntry.from_dict(json.loads(line)) for line in journal_lines]
        valid, chain_errors = verify_chain(entries)
        if not valid:
            errors.append("journal chain inconsistent")
            errors.extend(f"  {err}" for err in chain_errors)

        findings = json.loads(archive.read("findings.json"))
        decisions = json.loads(archive.read("decisions.json"))
        if manifest.get("findings_total") != len(findings):
            errors.append(f"findings_total {manifest.get('findings_total')} != actual {len(findings)}")
        if manifest.get("decisions_total") != len(decisions):
            errors.append(f"decisions_total {manifest.get('decisions_total')} != actual {len(decisions)}")

    return not errors, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a Kaypoh audit pack")
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

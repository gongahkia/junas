#!/usr/bin/env python3
"""Purge persisted anonymization mappings by hash or retention age."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from junas.anonymize.mapping_store import mapping_exists, purge_expired_mappings, purge_mapping  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Purge Junas persisted mapping-store entries")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--document-hash", help="delete one mapping by SHA-256 document hash")
    group.add_argument("--older-than-days", type=int, help="delete mappings older than this many days")
    parser.add_argument("--tenant", "--tenant-id", dest="tenant_id", help="tenant storage id")
    parser.add_argument("--dry-run", action="store_true", help="show retention matches without deleting")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    if args.document_hash:
        matched = mapping_exists(args.document_hash, tenant_id=args.tenant_id)
        deleted = False if args.dry_run else purge_mapping(args.document_hash, tenant_id=args.tenant_id)
        payload = {
            "mode": "document_hash",
            "document_hash": args.document_hash,
            "matched": matched,
            "deleted": deleted,
            "dry_run": bool(args.dry_run),
        }
    else:
        if args.older_than_days < 0:
            parser.error("--older-than-days must be >= 0")
        matches = purge_expired_mappings(
            older_than_days=args.older_than_days,
            dry_run=args.dry_run,
            tenant_id=args.tenant_id,
        )
        payload = {
            "mode": "retention",
            "older_than_days": args.older_than_days,
            "dry_run": bool(args.dry_run),
            "matched": len(matches),
            "mappings": matches,
        }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload["mode"] == "document_hash":
        action = (
            "would delete"
            if args.dry_run and payload["matched"]
            else "not found"
            if args.dry_run
            else "deleted"
            if payload["deleted"]
            else "not found"
        )
        print(f"{action}: {payload['document_hash']}")
    else:
        action = "would delete" if args.dry_run else "deleted"
        print(f"{action} {payload['matched']} mapping(s)")
        for item in payload["mappings"]:
            print(f"  - {item['document_hash']} {item['created_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

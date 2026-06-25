#!/usr/bin/env python3
"""Scan a neutral DMS export manifest with Junas review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from junas.integrations.dms import scan_manifest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan iManage/NetDocuments manifest exports")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profile", choices=("strict", "audit_grade"), default="strict")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    payload = scan_manifest(args.manifest, review_profile=args.profile)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

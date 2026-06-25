#!/usr/bin/env python3
"""Production preflight entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = ROOT / "scripts"
SRC = ROOT / "src"
for path in (SCRIPT_DIR, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import preflight  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if "--deployment" not in args:
        args.extend(["--deployment", "production"])
    if "--strict" not in args:
        args.append("--strict")
    prior = sys.argv
    try:
        sys.argv = ["preflight.py", *args]
        return preflight.main()
    finally:
        sys.argv = prior


if __name__ == "__main__":
    raise SystemExit(main())

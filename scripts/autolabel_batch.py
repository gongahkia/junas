#!/usr/bin/env python3
"""Batch wrapper for autolabel_fixture.py.

Walks the legal-corpus and legal-corpus-adversarial directories and runs the
auto-labeler on every fixture missing labels (or carrying a stub from
generate_legal_fixture.py). Human-labeled fixtures are protected by default;
pass --force to re-label them.

Usage:
    OPENAI_API_KEY=... python3 scripts/autolabel_batch.py
    OPENAI_API_KEY=... python3 scripts/autolabel_batch.py --model o1 --limit 5
    OPENAI_API_KEY=... python3 scripts/autolabel_batch.py --model gpt-4o --adversarial-only
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.autolabel_fixture import autolabel  # noqa: E402

CORPUS = REPO / "test" / "fixtures" / "legal-corpus"
ADV = REPO / "test" / "fixtures" / "legal-corpus-adversarial"


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch auto-labeler")
    parser.add_argument(
        "--model",
        default=os.environ.get("KAYPOH_AUTOLABEL_MODEL", "o1"),
        help="OpenAI model (default: o1)",
    )
    parser.add_argument("--force", action="store_true",
                        help="Re-label fixtures that already have labels (skips human-labeled)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Stop after N successful labelings (0 = no limit)")
    parser.add_argument("--corpus-only", action="store_true")
    parser.add_argument("--adversarial-only", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("OPENAI_API_KEY not set", file=sys.stderr)
        return 2

    dirs: list[Path] = []
    if not args.adversarial_only:
        dirs.append(CORPUS)
    if not args.corpus_only:
        dirs.append(ADV)

    fixtures: list[Path] = []
    for d in dirs:
        fixtures.extend(sorted(d.glob("*.txt")))

    print(f"model: {args.model}  fixtures discovered: {len(fixtures)}", flush=True)

    ok = skip = err = 0
    t_start = time.monotonic()
    for fx in fixtures:
        if args.limit and ok >= args.limit:
            break
        t_doc = time.monotonic()
        try:
            r = autolabel(fx, model=args.model, api_key=api_key, force=args.force)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {fx.name}: {exc}", flush=True)
            err += 1
            continue
        dt_ms = int((time.monotonic() - t_doc) * 1000)
        status = r.get("status", "")
        if status == "labeled":
            ok += 1
            print(f"  + {fx.name}  must={r['must_detect_count']} "
                  f"not={r['must_not_detect_count']} warn={r['warnings']} {dt_ms}ms",
                  flush=True)
        elif status.startswith("skipped"):
            skip += 1
            print(f"  - {fx.name}  ({status})", flush=True)
        else:
            err += 1
            print(f"  ! {fx.name}  {r}", flush=True)

    elapsed = int(time.monotonic() - t_start)
    print(f"\n=== summary ===")
    print(f"labeled: {ok}  skipped: {skip}  errors: {err}  elapsed: {elapsed}s")
    print("Spot-check at least 10% of auto-labeled fixtures before refreshing recall.lock.json.")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Batch wrapper for generate_legal_fixture.py.

Generates N fixtures per (doc_type × variant) in one shot. Skips slugs already on disk;
continues on per-fixture failures. Defaults to gpt-4o for the upgrade over gpt-4o-mini.

Usage:
    OPENAI_API_KEY=... python3 scripts/generate_legal_fixture_batch.py --count-per-type 4
    OPENAI_API_KEY=... python3 scripts/generate_legal_fixture_batch.py --count-per-type 6 --skip-adversarial

Hand-review of every labels.json stub remains mandatory before recall.lock refresh.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_legal_fixture import main as generate_one  # noqa: E402

DOC_TYPES = ["spa", "nda", "sha", "term_sheet", "memo", "research_note", "employment_letter"]
CORPUS_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus"
ADV_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus-adversarial"


def _next_slug(target_dir: Path, prefix: str) -> str:
    idx = 2
    while (target_dir / f"{prefix}_{idx:02d}.txt").exists():
        idx += 1
    return f"{prefix}_{idx:02d}"


def _run_one(doc_type: str, slug: str, *, adversarial: bool, multilingual: bool, model: str) -> int:
    argv = [doc_type, "--slug", slug, "--model", model]
    if adversarial:
        argv.append("--adversarial")
    if multilingual:
        argv.append("--multilingual")
    return generate_one(argv)


def _generate_pass(label: str, target_dir: Path, prefix_fn, *, count: int, adversarial: bool, model: str, multilingual_every: int) -> tuple[int, int]:
    succeeded = 0
    failed = 0
    print(f"=== {label}: {count}/type × {len(DOC_TYPES)} types ===", flush=True)
    for dt in DOC_TYPES:
        for n in range(count):
            slug = _next_slug(target_dir, prefix_fn(dt))
            multilingual = (n % multilingual_every == 0)
            tag = "ml" if multilingual else "en"
            t0 = time.monotonic()
            try:
                rc = _run_one(dt, slug, adversarial=adversarial, multilingual=multilingual, model=model)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {slug} [{tag}] crashed: {exc}", flush=True)
                failed += 1
                continue
            dt_ms = int((time.monotonic() - t0) * 1000)
            if rc == 0:
                print(f"  + {slug} [{tag}] {dt_ms}ms", flush=True)
                succeeded += 1
            else:
                print(f"  ! {slug} [{tag}] rc={rc}", flush=True)
                failed += 1
    return succeeded, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch fixture generator")
    parser.add_argument("--count-per-type", type=int, default=4, help="N per doc type per variant pass")
    parser.add_argument("--model", default=os.environ.get("KAYPOH_FIXTURE_MODEL", "gpt-4o"))
    parser.add_argument("--skip-default", action="store_true")
    parser.add_argument("--skip-adversarial", action="store_true")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print("OPENAI_API_KEY is not set", file=sys.stderr)
        return 2

    print(f"model: {args.model}  count-per-type: {args.count_per_type}", flush=True)

    total_ok = 0
    total_fail = 0
    t_start = time.monotonic()

    if not args.skip_default:
        ok, fail = _generate_pass(
            "default corpus",
            CORPUS_DIR,
            prefix_fn=lambda dt: dt,
            count=args.count_per_type,
            adversarial=False,
            model=args.model,
            multilingual_every=3,  # ~1 in 3 multilingual
        )
        total_ok += ok
        total_fail += fail

    if not args.skip_adversarial:
        ok, fail = _generate_pass(
            "adversarial corpus",
            ADV_DIR,
            prefix_fn=lambda dt: f"{dt}_adv",
            count=args.count_per_type,
            adversarial=True,
            model=args.model,
            multilingual_every=2,  # ~1 in 2 multilingual under adversarial
        )
        total_ok += ok
        total_fail += fail

    elapsed = int(time.monotonic() - t_start)
    print("\n=== summary ===")
    print(f"total ok: {total_ok}  failed: {total_fail}  elapsed: {elapsed}s")
    print("HAND-REVIEW each labels.json stub before refreshing recall.lock.json.")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

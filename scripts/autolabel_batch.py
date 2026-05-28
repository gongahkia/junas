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
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.autolabel_fixture import _azure_env, _existing_is_human, autolabel, label_model_for_provider  # noqa: E402

CORPUS = REPO / "test" / "fixtures" / "legal-corpus"
ADV = REPO / "test" / "fixtures" / "legal-corpus-adversarial"
CANDIDATES = REPO / "test" / "fixtures" / "legal-corpus-candidates"


def _provider_label_model(provider: str, model: str) -> str:
    return label_model_for_provider(provider, model)


def _label_one(fx: Path, *, model: str, api_key: str, force: bool, provider: str) -> dict:
    t_doc = time.monotonic()
    try:
        result = autolabel(fx, model=model, api_key=api_key, force=force, provider=provider)
        return {
            "fixture": fx,
            "result": result,
            "dt_ms": int((time.monotonic() - t_doc) * 1000),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "fixture": fx,
            "exception": exc,
            "dt_ms": int((time.monotonic() - t_doc) * 1000),
        }


def _skip_status(fx: Path, *, label_model: str, force: bool) -> str:
    labels_path = fx.with_suffix(".labels.json")
    if not labels_path.exists():
        return ""
    if _existing_is_human(labels_path):
        return "skipped_human_labeled"
    if force:
        return ""
    try:
        import json

        existing = json.loads(labels_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    existing_model = existing.get("_label_model")
    if existing_model == label_model:
        return "skipped_same_model"
    if label_model.startswith("openai:") and existing_model == label_model.split(":", 1)[1]:
        return "skipped_same_model"
    return ""


def _skip_payload(fx: Path, status: str) -> dict:
    return {
        "fixture": fx,
        "result": {"status": status, "path": str(fx.with_suffix(".labels.json"))},
        "dt_ms": 0,
    }


def _is_auth_failure(payload: dict) -> bool:
    text = ""
    if "exception" in payload:
        text = str(payload["exception"])
    else:
        text = str(payload.get("result", {}).get("error", ""))
    return "OpenAI 401" in text or "invalid_api_key" in text


def _record_result(payload: dict) -> tuple[int, int, int]:
    fx = payload["fixture"]
    dt_ms = payload["dt_ms"]
    if "exception" in payload:
        print(f"  ! {fx.name}: {payload['exception']}", flush=True)
        return 0, 0, 1

    r = payload["result"]
    status = r.get("status", "")
    if status == "labeled":
        print(
            f"  + {fx.name}  must={r['must_detect_count']} "
            f"not={r['must_not_detect_count']} warn={r['warnings']} {dt_ms}ms",
            flush=True,
        )
        return 1, 0, 0
    if status.startswith("skipped"):
        print(f"  - {fx.name}  ({status})", flush=True)
        return 0, 1, 0

    print(f"  ! {fx.name}  {r}", flush=True)
    return 0, 0, 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch auto-labeler")
    parser.add_argument(
        "--model",
        default=os.environ.get("KAYPOH_AUTOLABEL_MODEL", "o1"),
        help="OpenAI model (default: o1)",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "azure"),
        default=os.environ.get("KAYPOH_AUTOLABEL_PROVIDER", "openai"),
        help="Model provider (default: openai, env KAYPOH_AUTOLABEL_PROVIDER)",
    )
    parser.add_argument("--force", action="store_true",
                        help="Re-label fixtures that already have labels (skips human-labeled)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Stop after N successful labelings (0 = no limit)")
    parser.add_argument("--corpus-only", action="store_true")
    parser.add_argument("--adversarial-only", action="store_true")
    parser.add_argument("--candidate-only", action="store_true")
    parser.add_argument("--candidate-dir", type=Path, default=CANDIDATES)
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("KAYPOH_AUTOLABEL_WORKERS", "1")),
        help="Parallel OpenAI calls to run (default: 1, env KAYPOH_AUTOLABEL_WORKERS)",
    )
    args = parser.parse_args()

    if args.provider == "azure":
        api_key = _azure_env(
            "KAYPOH_AUTOLABEL_AZURE_API_KEY",
            "GPT5_MINI_API_KEY",
            "GPT5_PRO_API_KEY",
            "AZURE_OPENAI_API_KEY",
        )
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print(f"{args.provider} API key not set", file=sys.stderr)
        return 2

    dirs: list[Path] = []
    if args.candidate_only:
        dirs.append(args.candidate_dir if args.candidate_dir.is_absolute() else REPO / args.candidate_dir)
    else:
        if not args.adversarial_only:
            dirs.append(CORPUS)
        if not args.corpus_only:
            dirs.append(ADV)

    fixtures: list[Path] = []
    for d in dirs:
        fixtures.extend(sorted(d.glob("**/*.txt")))

    workers = max(1, args.workers)
    if args.limit and workers > 1:
        print("--limit requested; running sequentially so the successful-label cap is exact.", flush=True)
        workers = 1

    print(
        f"provider: {args.provider}  model: {args.model}  fixtures discovered: {len(fixtures)}  workers: {workers}",
        flush=True,
    )
    label_model = _provider_label_model(args.provider, args.model)

    ok = skip = err = 0
    t_start = time.monotonic()
    if workers == 1:
        for fx in fixtures:
            if args.limit and ok >= args.limit:
                break
            payload = _label_one(
                fx, model=args.model, api_key=api_key, force=args.force, provider=args.provider
            )
            d_ok, d_skip, d_err = _record_result(payload)
            ok += d_ok
            skip += d_skip
            err += d_err
            if _is_auth_failure(payload):
                print("aborting remaining fixtures after OpenAI authentication failure.", flush=True)
                break
    else:
        pending: list[Path] = []
        for fx in fixtures:
            status = _skip_status(fx, label_model=label_model, force=args.force)
            if status:
                d_ok, d_skip, d_err = _record_result(_skip_payload(fx, status))
                ok += d_ok
                skip += d_skip
                err += d_err
            else:
                pending.append(fx)

        pending_iter = iter(pending)
        active = set()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            def submit_next() -> None:
                try:
                    fx = next(pending_iter)
                except StopIteration:
                    return
                active.add(pool.submit(
                    _label_one,
                    fx,
                    model=args.model,
                    api_key=api_key,
                    force=args.force,
                    provider=args.provider,
                ))

            for _ in range(min(workers, len(pending))):
                submit_next()

            abort_for_auth = False
            while active:
                done, active = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    payload = future.result()
                    d_ok, d_skip, d_err = _record_result(payload)
                    ok += d_ok
                    skip += d_skip
                    err += d_err
                    if _is_auth_failure(payload):
                        abort_for_auth = True
                    elif not abort_for_auth:
                        submit_next()
                if abort_for_auth:
                    for future in active:
                        future.cancel()
                    print("aborting remaining fixtures after OpenAI authentication failure.", flush=True)
                    break

    elapsed = int(time.monotonic() - t_start)
    print("\n=== summary ===")
    print(f"labeled: {ok}  skipped: {skip}  errors: {err}  elapsed: {elapsed}s")
    print("Spot-check at least 10% of auto-labeled fixtures before refreshing recall.lock.json.")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

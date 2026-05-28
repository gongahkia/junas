#!/usr/bin/env python3
"""Run the candidate fixture generation/autolabel/evaluation pipeline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"
AZURE_ENV_GROUPS = (
    (
        "KAYPOH_AUTOLABEL_AZURE_API_KEY",
        "GPT5_MINI_API_KEY",
        "GPT5_PRO_API_KEY",
        "AZURE_OPENAI_API_KEY",
    ),
    (
        "KAYPOH_AUTOLABEL_AZURE_ENDPOINT",
        "GPT5_MINI_ENDPOINT",
        "GPT5_PRO_ENDPOINT",
    ),
    (
        "KAYPOH_AUTOLABEL_AZURE_DEPLOYMENT",
        "GPT5_MINI_DEPLOYMENT",
        "GPT5_PRO_DEPLOYMENT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_DEPLOYMENT",
    ),
    (
        "KAYPOH_AUTOLABEL_AZURE_API_VERSION",
        "GPT5_MINI_API_VERSION",
        "GPT5_PRO_API_VERSION",
        "AZURE_OPENAI_API_VERSION",
    ),
)


def _default_run_dir() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    return Path(f"/tmp/kaypoh-candidate-run-{stamp}")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _missing_env(*names: str) -> list[str]:
    return [name for name in names if not os.environ.get(name, "").strip()]


def _missing_env_groups(groups: tuple[tuple[str, ...], ...]) -> list[str]:
    return [" or ".join(group) for group in groups if not any(os.environ.get(name, "").strip() for name in group)]


def _load_env_file(path: Path) -> int:
    if not path.exists():
        return 0
    loaded = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not (key[0].isalpha() or key[0] == "_"):
            continue
        if not all(char.isalnum() or char == "_" for char in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


def _append_event(run_dir: Path, payload: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "pipeline_manifest.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _run(
    cmd: list[str],
    *,
    run_dir: Path,
    step: str,
    accepted_returncodes: set[int] | None = None,
) -> int:
    accepted = accepted_returncodes or {0}
    started = time.time()
    print(f"\n=== {step} ===", flush=True)
    print(" ".join(cmd), flush=True)
    _append_event(run_dir, {"event": "start", "step": step, "cmd": cmd, "ts_unix": int(started)})
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True)
    elapsed = int(time.time() - started)
    _append_event(
        run_dir,
        {
            "event": "finish",
            "step": step,
            "cmd": cmd,
            "returncode": result.returncode,
            "elapsed_seconds": elapsed,
        },
    )
    if result.returncode not in accepted:
        print(f"{step} failed with return code {result.returncode}", file=sys.stderr)
    return result.returncode


def _print_or_run(
    cmd: list[str],
    *,
    dry_run: bool,
    run_dir: Path,
    step: str,
    accepted_returncodes: set[int] | None = None,
) -> int:
    if dry_run:
        print(f"\n=== {step} ===")
        print(" ".join(cmd))
        _append_event(run_dir, {"event": "dry_run", "step": step, "cmd": cmd})
        return 0
    return _run(cmd, run_dir=run_dir, step=step, accepted_returncodes=accepted_returncodes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run candidate fixture corpus pipeline")
    parser.add_argument("--profile", default="saturation-4284", choices=("custom", "saturation-4284"))
    parser.add_argument("--candidate-dir", type=Path, default=DEFAULT_CANDIDATE_DIR)
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--generation-model", default=os.environ.get("KAYPOH_FIXTURE_MODEL", "gpt-4o"))
    parser.add_argument("--autolabel-model", default=os.environ.get("KAYPOH_AUTOLABEL_MODEL", "o1"))
    parser.add_argument("--workers", type=int, default=int(os.environ.get("KAYPOH_AUTOLABEL_WORKERS", "1")))
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--no-env-file", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--label-only", action="store_true")
    parser.add_argument("--evaluate-only", action="store_true")
    args = parser.parse_args(argv)

    candidate_dir = _resolve(args.candidate_dir)
    run_dir = _resolve(args.run_dir) if args.run_dir else _default_run_dir()
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"run_dir: {run_dir}")
    if not args.no_env_file:
        env_file = _resolve(args.env_file)
        loaded = _load_env_file(env_file)
        if env_file.exists():
            print(f"loaded env file: {env_file} ({loaded} new keys)")

    if sum(bool(flag) for flag in (args.generate_only, args.label_only, args.evaluate_only)) > 1:
        print("choose at most one of --generate-only, --label-only, --evaluate-only", file=sys.stderr)
        return 2

    if not args.dry_run:
        missing: list[str] = []
        if not args.label_only and not args.evaluate_only:
            missing.extend(_missing_env("OPENAI_API_KEY"))
        if not args.generate_only and not args.evaluate_only:
            missing.extend(_missing_env_groups(AZURE_ENV_GROUPS))
        if missing:
            print("missing required env vars:", file=sys.stderr)
            for name in sorted(set(missing)):
                print(f"  - {name}", file=sys.stderr)
            print("Use --dry-run to inspect commands without provider credentials.", file=sys.stderr)
            return 2

    rc = 0
    if not args.label_only and not args.evaluate_only:
        generation_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "generate_candidate_corpus.py"),
            "--profile",
            args.profile,
            "--out-dir",
            str(candidate_dir),
            "--model",
            args.generation_model,
            "--manifest-dir",
            str(run_dir),
        ]
        if args.dry_run:
            generation_cmd.append("--dry-run")
        rc = _print_or_run(generation_cmd, dry_run=False, run_dir=run_dir, step="generate")
        if rc != 0:
            return rc

    if not args.generate_only and not args.evaluate_only:
        label_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "autolabel_batch.py"),
            "--candidate-only",
            "--candidate-dir",
            str(candidate_dir),
            "--provider",
            "azure",
            "--model",
            args.autolabel_model,
            "--workers",
            str(max(1, args.workers)),
        ]
        rc = _print_or_run(label_cmd, dry_run=args.dry_run, run_dir=run_dir, step="autolabel")
        if rc != 0:
            return rc

    if not args.generate_only and not args.label_only:
        evaluation_path = run_dir / "candidate_evaluation.json"
        evaluate_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "evaluate_candidate_corpus.py"),
            "--corpus",
            str(candidate_dir),
            "--output",
            str(evaluation_path),
        ]
        rc = _print_or_run(evaluate_cmd, dry_run=args.dry_run, run_dir=run_dir, step="evaluate")
        if rc != 0:
            return rc
        review_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "check_candidate_review_status.py"),
            "--corpus",
            str(candidate_dir),
        ]
        rc = _print_or_run(
            review_cmd,
            dry_run=args.dry_run,
            run_dir=run_dir,
            step="review-status-pending-check",
            accepted_returncodes={0, 1},
        )
        if rc == 1:
            print("review-status check found pending generated labels, as expected for quarantine candidates.")
            rc = 0
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run locked-corpus recall gates when policy/rewrite paths change."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
WATCHED_PATH_PREFIXES = (
    "src/junas/policy/",
    "src/junas/anonymize/",
    "src/junas/backend/",
)
WATCHED_PATHS = frozenset({
    "src/junas/policy/config.py",
    "src/junas/policy/engine.py",
    "src/junas/anonymize/engine.py",
    "src/junas/backend/main.py",
})
DEFAULT_CORPORA = (
    Path("test/fixtures/legal-corpus"),
    Path("test/fixtures/legal-corpus-adversarial"),
    Path("test/fixtures/legal-corpus-sea"),
    Path("test/fixtures/legal-corpus-hk-au-jp-kr"),
    Path("test/fixtures/legal-corpus-cn"),
    Path("test/fixtures/legal-corpus-in"),
    Path("test/fixtures/legal-corpus-ae"),
    Path("test/fixtures/legal-corpus-sa"),
    Path("test/fixtures/legal-corpus-reviewed-candidates"),
)


def _normalize(path: str | Path) -> str:
    return Path(path).as_posix().lstrip("./")


def path_triggers_false_negative_gate(path: str | Path) -> bool:
    normalized = _normalize(path)
    return normalized in WATCHED_PATHS or any(
        normalized.startswith(prefix) for prefix in WATCHED_PATH_PREFIXES
    )


def changed_paths_from_git(base_ref: str, head_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", base_ref, head_ref],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git diff failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def triggered_paths(changed_paths: list[str]) -> list[str]:
    return sorted(_normalize(path) for path in changed_paths if path_triggers_false_negative_gate(path))


def run_recall_gates(corpora: list[Path]) -> list[dict[str, Any]]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    results: list[dict[str, Any]] = []
    for corpus in corpora:
        corpus_path = corpus if corpus.is_absolute() else REPO_ROOT / corpus
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "recall_gate.py"),
            "--corpus",
            str(corpus_path),
        ]
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        results.append({
            "corpus": str(corpus),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        })
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail if policy/rewrite changes regress locked legal-corpus recall"
    )
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--always-run", action="store_true")
    parser.add_argument("--corpus", type=Path, action="append", default=[])
    args = parser.parse_args(argv)

    changed: list[str] = []
    if not args.always_run:
        if not args.base_ref:
            print("--base-ref is required unless --always-run is set", file=sys.stderr)
            return 2
        try:
            changed = changed_paths_from_git(args.base_ref, args.head_ref)
        except RuntimeError as exc:
            print(f"false-negative risk gate failed before eval: {exc}", file=sys.stderr)
            return 2
        triggers = triggered_paths(changed)
        if not triggers:
            print("no policy/rewrite changes; false-negative risk gate skipped")
            return 0
        print("policy/rewrite changes require locked-corpus recall gates:")
        for path in triggers:
            print(f"  {path}")

    corpora = args.corpus or list(DEFAULT_CORPORA)
    results = run_recall_gates(corpora)
    failures = [item for item in results if item["returncode"] != 0]
    for item in results:
        print(f"{item['corpus']}: recall_gate exit={item['returncode']}")
    if failures:
        for item in failures:
            print(f"false-negative risk gate failed for {item['corpus']}", file=sys.stderr)
            if item["stdout"]:
                print(item["stdout"], file=sys.stderr)
            if item["stderr"]:
                print(item["stderr"], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

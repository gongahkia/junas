#!/usr/bin/env python3
"""Verify, sync, and regenerate Kaypoh runtime artifacts."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kaypoh.configs.artifacts import (
    artifact_manifest_path,
    sync_legacy_artifacts,
    verify_artifact_manifest,
    write_artifact_manifest,
)


def _git_revision() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True)
            .strip()
        )
    except Exception:
        return "unknown"


def _run_training() -> None:
    python_exec = ROOT / ".venv" / "bin" / "python"
    cmd = [
        str(python_exec if python_exec.exists() else Path(sys.executable)),
        str(ROOT / "training" / "train_validate_pipeline.py"),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or bootstrap Kaypoh runtime artifacts")
    parser.add_argument("--manifest", type=str, help="override artifact manifest path")
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="rewrite the manifest from the currently available artifact sources",
    )
    parser.add_argument(
        "--sync-from-legacy",
        action="store_true",
        help="copy artifacts from legacy backend/workflow checkpoints into artifacts/",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="run the full training pipeline if verification still fails",
    )
    args = parser.parse_args()

    manifest_path = artifact_manifest_path(args.manifest)
    revision = _git_revision()

    if args.update_manifest or not manifest_path.exists():
        manifest_path = write_artifact_manifest(
            training_revision=revision,
            manifest_path=manifest_path,
            prefer_target=False,
        )
        print(f"wrote artifact manifest: {manifest_path}")

    if args.sync_from_legacy:
        copied = sync_legacy_artifacts(manifest_path)
        if copied:
            for path in copied:
                print(f"hydrated artifact: {path}")
        else:
            print("no legacy artifacts were copied")

    errors = verify_artifact_manifest(manifest_path)
    if not errors:
        print(f"artifact manifest verified: {manifest_path}")
        return 0

    print("artifact verification failed:")
    for error in errors:
        print(f"  - {error}")

    if not args.regenerate:
        print("next:")
        print("  - Run with --sync-from-legacy to hydrate artifacts from legacy checkpoints")
        print("  - Or run with --regenerate to retrain the full pipeline and refresh the manifest")
        return 1

    _run_training()
    write_artifact_manifest(
        training_revision=_git_revision(),
        manifest_path=manifest_path,
        prefer_target=False,
    )
    errors = verify_artifact_manifest(manifest_path)
    if errors:
        print("artifact verification still failing after regeneration:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"artifact manifest verified after regeneration: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

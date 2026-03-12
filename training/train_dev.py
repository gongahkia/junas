#!/usr/bin/env python3
"""Interactive launcher for Noupe training scripts."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAINING_ROOT = ROOT / "training"

TRAINING_TARGETS = {
    "classification": {
        "label": "Classification-only training",
        "script": TRAINING_ROOT / "train_validate_classification.py",
        "description": (
            "Document-level 80/20 split for the supervised classifiers only. "
            "Trains Model 1 and Model 2, then prints train/validation F1 reports."
        ),
    },
    "pipeline": {
        "label": "Full pipeline training",
        "script": TRAINING_ROOT / "train_validate_pipeline.py",
        "description": (
            "Two-pass end-to-end pipeline training. "
            "Trains classification, clustering, and regression artifacts, "
            "then validates complete pipeline configurations and writes a report."
        ),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch a Noupe training workflow")
    parser.add_argument(
        "target",
        nargs="?",
        choices=sorted(TRAINING_TARGETS.keys()),
        help="Training workflow to run",
    )
    parser.add_argument(
        "target_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments to pass to the selected training script",
    )
    return parser.parse_args()


def print_menu() -> None:
    print("Available training workflows:")
    print("")
    print("1) classification")
    print(f"   {TRAINING_TARGETS['classification']['description']}")
    print("")
    print("2) pipeline")
    print(f"   {TRAINING_TARGETS['pipeline']['description']}")
    print("")


def prompt_target() -> str:
    if not sys.stdin.isatty():
        raise SystemExit("Non-interactive terminal: pass 'classification' or 'pipeline' explicitly.")

    while True:
        print_menu()
        selection = input("Select a training workflow [1]: ").strip().lower()

        if selection in {"", "1", "classification"}:
            return "classification"
        if selection in {"2", "pipeline"}:
            return "pipeline"

        print("Unrecognized selection. Choose 1 or 2.")
        print("")


def normalize_target_args(raw_args: list[str]) -> list[str]:
    if raw_args and raw_args[0] == "--":
        return raw_args[1:]
    return raw_args


def main() -> int:
    args = parse_args()
    target = args.target or prompt_target()
    target_args = normalize_target_args(args.target_args)

    target_meta = TRAINING_TARGETS[target]
    script_path = target_meta["script"]

    print(f"Selected: {target_meta['label']}")
    print(target_meta["description"])
    print(f"Running: {script_path}")
    if target_args:
        print(f"Arguments: {' '.join(target_args)}")

    cmd = [sys.executable, str(script_path), *target_args]
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())

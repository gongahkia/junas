#!/usr/bin/env python3
"""Fetch the English ai4privacy pii-masking-200k fixture without extra deps."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_DIR = REPO_ROOT / "test" / "fixtures" / "external" / "ai4privacy-pii-masking-200k"
DATASET_ID = "ai4privacy/pii-masking-200k"
BASE_URL = f"https://huggingface.co/datasets/{DATASET_ID}/resolve/main"
API_TREE_URL = f"https://huggingface.co/api/datasets/{DATASET_ID}/tree/main"
FILES = ("english_pii_43k.jsonl", "summary.json", "pii_class_counts.json", "README.md", "LICENSE")
MANIFEST_NAME = "fixture_manifest.json"


def _chmod_tree(path: Path, mode_fn) -> None:
    if not path.exists():
        return
    for item in sorted(path.rglob("*"), reverse=True):
        try:
            os.chmod(item, mode_fn(item.stat().st_mode))
        except FileNotFoundError:
            pass
    os.chmod(path, mode_fn(path.stat().st_mode))


def _make_writable(path: Path) -> None:
    _chmod_tree(path, lambda mode: mode | stat.S_IWUSR)


def _make_read_only(path: Path) -> None:
    _chmod_tree(path, lambda mode: mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _fetch_tree_metadata() -> dict[str, dict[str, Any]]:
    with urllib.request.urlopen(API_TREE_URL, timeout=60) as response:
        payload = json.load(response)
    return {str(item.get("path")): item for item in payload if isinstance(item, dict)}


def _download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)


def fetch_fixture(dest: Path, *, force: bool = False) -> Path:
    _make_writable(dest)
    dest.mkdir(parents=True, exist_ok=True)
    metadata = _fetch_tree_metadata()
    manifest: dict[str, Any] = {
        "dataset": DATASET_ID,
        "source": BASE_URL,
        "downloaded_at_unix": int(time.time()),
        "files": {},
    }
    for filename in FILES:
        path = dest / filename
        if force or not path.is_file():
            _download(f"{BASE_URL}/{filename}", path)
        item = metadata.get(filename, {})
        manifest["files"][filename] = {
            "size": path.stat().st_size,
            "oid": item.get("oid", ""),
            "lfs_oid": (item.get("lfs") or {}).get("oid", "") if isinstance(item.get("lfs"), dict) else "",
            "xet_hash": item.get("xetHash", ""),
        }
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _make_read_only(dest)
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch ignored ai4privacy pii-masking-200k fixture files")
    parser.add_argument("--dest", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    dest = args.dest if args.dest.is_absolute() else REPO_ROOT / args.dest
    try:
        fixture = fetch_fixture(dest, force=args.force)
    except Exception as exc:
        print(f"failed to fetch ai4privacy fixture: {exc}", file=sys.stderr)
        return 1
    print(fixture)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASK = ROOT / "packaging" / "homebrew" / "Casks" / "aki.rb"

VERSION_RE = re.compile(r'(?m)^  version "[^"]+"$')
SHA_RE = re.compile(r'(?m)^  sha256 "[a-f0-9]{64}"$')
URL_TOKEN = 'url "https://github.com/gongahkia/junas/releases/download/v#{version}/JunasMenuBar-#{version}.dmg"'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def update_cask_text(text: str, *, version: str, sha256: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?", version):
        raise ValueError(f"invalid cask version: {version!r}")
    if not re.fullmatch(r"[a-f0-9]{64}", sha256):
        raise ValueError("sha256 must be 64 lowercase hex characters")
    if URL_TOKEN not in text:
        raise ValueError("cask URL does not match JunasMenuBar release asset template")
    text, version_count = VERSION_RE.subn(f'  version "{version}"', text, count=1)
    text, sha_count = SHA_RE.subn(f'  sha256 "{sha256}"', text, count=1)
    if version_count != 1:
        raise ValueError("expected exactly one cask version stanza")
    if sha_count != 1:
        raise ValueError("expected exactly one cask sha256 stanza")
    return text


def update_cask(cask_path: Path, *, version: str, dmg_path: Path) -> str:
    if not dmg_path.is_file():
        raise FileNotFoundError(f"DMG not found: {dmg_path}")
    digest = sha256_file(dmg_path)
    text = cask_path.read_text(encoding="utf-8")
    cask_path.write_text(update_cask_text(text, version=version, sha256=digest), encoding="utf-8")
    return digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update staged Homebrew cask version and SHA-256 from a DMG.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--dmg", required=True, type=Path)
    parser.add_argument("--cask", default=DEFAULT_CASK, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        digest = update_cask(args.cask, version=args.version, dmg_path=args.dmg)
    except Exception as exc:
        sys.stderr.write(f"failed to update cask: {exc}\n")
        return 1
    print(f"{args.cask}: version={args.version} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

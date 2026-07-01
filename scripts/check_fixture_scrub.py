#!/usr/bin/env python3
"""Fail if committed fixture/report artifacts contain secrets or reversible mappings."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent

TARGET_PREFIXES = ("test/fixtures/", "reports/")
TARGET_SUFFIXES = (
    ".history.jsonl",
    ".labels.json",
    ".lock.json",
    ".report.json",
    ".report.jsonl",
    ".sidecar.json",
)


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule: str
    excerpt: str


RULES = (
    Rule("deleted journal default key", re.compile(r"junas-default-dev-key")),
    Rule("plaintext mapping store marker", re.compile(r"plaintext-v1")),
    Rule("reversible mapping value", re.compile(r'"original_text"\s*:')),
    Rule("private key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    Rule("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    Rule("github token", re.compile(r"\bgh[opsu]_[A-Za-z0-9_]{30,}\b")),
    Rule("openai api key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    Rule("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    Rule("slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")),
    Rule(
        "junas secret env assignment",
        re.compile(r"\bJUNAS_(?:API|JOURNAL|MAPPING_STORE|SUBJECT_INDEX)_(?:KEY|SECRET)\s*="),
    ),
)


def _git_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def is_target(path: Path) -> bool:
    normalized = path.as_posix()
    return normalized.startswith(TARGET_PREFIXES) or normalized.endswith(TARGET_SUFFIXES)


def iter_target_files(paths: Iterable[Path]) -> list[Path]:
    return sorted(path for path in paths if is_target(path))


def _excerpt(line: str) -> str:
    cleaned = line.strip()
    return cleaned[:160] + ("...[truncated]" if len(cleaned) > 160 else "")


def scan_file(path: Path) -> list[Finding]:
    full_path = ROOT / path
    try:
        text = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            if rule.pattern.search(line):
                findings.append(Finding(path=path, line=line_number, rule=rule.name, excerpt=_excerpt(line)))
    return findings


def scan_paths(paths: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_target_files(paths):
        findings.extend(scan_file(path))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan committed fixture/report artifacts for secret regressions")
    parser.add_argument("paths", nargs="*", type=Path, help="optional repository-relative paths to scan")
    args = parser.parse_args(argv)

    candidate_paths = args.paths if args.paths else _git_files()
    findings = scan_paths(candidate_paths)
    if findings:
        for finding in findings:
            print(
                f"{finding.path}:{finding.line}: {finding.rule}: {finding.excerpt}",
                file=sys.stderr,
            )
        return 1
    print(f"fixture scrub passed ({len(iter_target_files(candidate_paths))} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

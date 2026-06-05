"""Validate dataset extraction-rule provenance fields."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

_SHA_RE = re.compile(r"^[0-9a-f]{7}$")
_YAML_SUFFIXES = {".yaml", ".yml"}


@dataclass(frozen=True)
class ValidationIssue:
    path: Path
    message: str


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_short_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA_RE.match(value))


def _validate_rules(path: Path, rules: Any) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(rules, dict):
        return [ValidationIssue(path, "missing or invalid top-level extraction_rules map")]
    for name, sha in rules.items():
        if not str(name).strip():
            issues.append(ValidationIssue(path, "extraction_rules contains an empty module name"))
        if not _is_short_sha(sha):
            issues.append(ValidationIssue(path, f"invalid extraction_rules SHA for {name!r}: {sha!r}"))
    return issues


def validate_yaml(path: Path, *, require_declared: bool = True) -> list[ValidationIssue]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return [ValidationIssue(path, "YAML root must be a mapping")]
    if "extraction_rules" not in payload and not require_declared:
        return []
    issues = _validate_rules(path, payload.get("extraction_rules"))
    cases = payload.get("cases") or []
    if not isinstance(cases, list):
        return issues + [ValidationIssue(path, "cases must be a list")]
    if cases and not payload.get("extraction_rules"):
        issues.append(ValidationIssue(path, "non-empty dataset has no extraction_rules entries"))
    declared_shas = set()
    if isinstance(payload.get("extraction_rules"), dict):
        declared_shas = {
            sha
            for sha in payload["extraction_rules"].values()
            if _is_short_sha(sha)
        }
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            issues.append(ValidationIssue(path, f"case[{idx}] must be a mapping"))
            continue
        sha = case.get("extraction_rule_sha")
        if not _is_short_sha(sha):
            name = case.get("name", f"case[{idx}]")
            issues.append(ValidationIssue(path, f"{name}: missing or invalid extraction_rule_sha"))
        elif declared_shas and sha not in declared_shas:
            name = case.get("name", f"case[{idx}]")
            issues.append(ValidationIssue(path, f"{name}: extraction_rule_sha not declared in extraction_rules"))
    return issues


def validate_jsonl(path: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(ValidationIssue(path, f"line {line_no}: invalid JSON: {exc}"))
            continue
        if not isinstance(row, dict):
            issues.append(ValidationIssue(path, f"line {line_no}: row must be a mapping"))
            continue
        sha = row.get("extraction_rule_sha")
        if not _is_short_sha(sha):
            row_id = row.get("id") or row.get("name") or f"line {line_no}"
            issues.append(ValidationIssue(path, f"{row_id}: missing or invalid extraction_rule_sha"))
    return issues


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(
                p
                for p in path.rglob("*")
                if p.suffix.lower() in _YAML_SUFFIXES or p.suffix.lower() == ".jsonl"
            )
        else:
            yield path


def validate_paths(paths: Iterable[Path], *, require_declared: bool) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for path in _iter_files(paths):
        if path.suffix.lower() in _YAML_SUFFIXES:
            issues.extend(validate_yaml(path, require_declared=require_declared))
        elif path.suffix.lower() == ".jsonl":
            if require_declared:
                issues.extend(validate_jsonl(path))
    return issues


def _default_paths() -> list[Path]:
    return [_backend_root() / "benchmark" / "datasets"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmark.dataset_validator")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument(
        "--require-declared",
        action="store_true",
        help="fail YAML files that do not declare extraction_rules",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    paths = args.paths or _default_paths()
    require_declared = bool(args.require_declared or args.paths)
    issues = validate_paths(paths, require_declared=require_declared)
    if issues:
        for issue in issues:
            print(f"{issue.path}: {issue.message}", file=sys.stderr)
        return 1
    print("dataset extraction provenance validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

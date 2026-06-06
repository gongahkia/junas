"""CI guard for synthetic candidate promotion state."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

APPROVED = "approved"
YAML_SUFFIXES = {".yaml", ".yml"}


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_dataset_root() -> Path:
    return Path(__file__).resolve().parents[1] / "datasets"


def _yaml_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(item for item in path.glob("*") if item.suffix.lower() in YAML_SUFFIXES)


def _cases_from(path: Path) -> tuple[list[dict[str, Any]], str]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [], f"unreadable YAML: {exc}"
    if not isinstance(payload, dict):
        return [], "YAML root must be a mapping"
    cases = payload.get("cases") or []
    if not isinstance(cases, list):
        return [], "cases must be a list"
    invalid = [idx for idx, case in enumerate(cases) if not isinstance(case, dict)]
    if invalid:
        return [], f"cases must contain mappings only; invalid indexes: {invalid}"
    return cases, ""


def _path_keys(path: Path, *, root: Path) -> set[str]:
    resolved = path.resolve()
    keys = {path.name, path.stem, str(path), str(resolved)}
    for base in (root, root.parent, _backend_root(), _backend_root().parent, Path.cwd()):
        try:
            keys.add(str(resolved.relative_to(base.resolve())))
        except ValueError:
            continue
    return keys


def _recorded_path_keys(raw: Any) -> set[str]:
    text = str(raw or "").strip()
    if not text:
        return set()
    path = Path(text)
    keys = {text, path.name, path.stem}
    bases = (_backend_root(), _backend_root().parent, Path.cwd())
    if path.is_absolute():
        keys.add(str(path.resolve()))
        return keys
    for base in bases:
        candidate = (base / path).resolve()
        keys.add(str(candidate))
        for rel_base in bases:
            try:
                keys.add(str(candidate.relative_to(rel_base.resolve())))
            except ValueError:
                continue
    return keys


def _reviewed_references(root: Path, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for reviewed_dir in sorted(path for path in root.glob("*_reviewed") if path.is_dir()):
        for path in _yaml_files(reviewed_dir):
            cases, error = _cases_from(path)
            if error:
                issues.append({"path": str(path), "message": error})
                continue
            for index, case in enumerate(cases):
                metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
                promotion = metadata.get("_promotion") if isinstance(metadata.get("_promotion"), dict) else {}
                refs.append(
                    {
                        "path": path,
                        "index": index,
                        "case_name": str(case.get("name") or ""),
                        "fixture_keys": _path_keys(path, root=root),
                        "source_keys": _recorded_path_keys(promotion.get("source_fixture")),
                        "promotion_case_name": str(promotion.get("case_name") or ""),
                    }
                )
    return refs


def _matching_reviewed_refs(candidate_path: Path, case_name: str, refs: list[dict[str, Any]], root: Path) -> list[str]:
    candidate_keys = _path_keys(candidate_path, root=root)
    matches: list[str] = []
    for ref in refs:
        ref_case_name = ref["case_name"]
        promotion_case_name = ref["promotion_case_name"]
        if case_name and (case_name == ref_case_name or case_name == promotion_case_name):
            matches.append(f"{ref['path']}#case[{ref['index']}]")
            continue
        if candidate_keys & ref["fixture_keys"] or candidate_keys & ref["source_keys"]:
            matches.append(f"{ref['path']}#case[{ref['index']}]")
    return matches


def validate_synthetic_promotion_guard(*, base_dir: Path | None = None) -> dict[str, Any]:
    root = base_dir or _default_dataset_root()
    issues: list[dict[str, Any]] = []
    refs = _reviewed_references(root, issues)
    candidate_count = 0
    for candidate_dir in sorted(path for path in root.glob("*_candidates") if path.is_dir()):
        for path in _yaml_files(candidate_dir):
            cases, error = _cases_from(path)
            if error:
                issues.append({"path": str(path), "message": error})
                continue
            for index, case in enumerate(cases):
                candidate_count += 1
                metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
                review_status = str(metadata.get("review_status") or "missing")
                if review_status == APPROVED:
                    continue
                case_name = str(case.get("name") or "")
                matches = _matching_reviewed_refs(path, case_name, refs, root)
                if matches:
                    issues.append(
                        {
                            "path": str(path),
                            "case_index": index,
                            "case_name": case_name,
                            "review_status": review_status,
                            "message": "non-approved synthetic candidate is referenced by reviewed-tier YAML",
                            "reviewed_references": matches,
                        }
                    )
    return {
        "ok": not issues,
        "candidate_count": candidate_count,
        "reviewed_reference_count": len(refs),
        "issues": issues,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmark.synthetic.validator")
    parser.add_argument("--base-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = validate_synthetic_promotion_guard(base_dir=args.base_dir)
    if result["ok"]:
        print("synthetic promotion validation passed")
        return 0
    for issue in result["issues"]:
        details = ""
        if issue.get("reviewed_references"):
            details = f" referenced by {', '.join(issue['reviewed_references'])}"
        print(f"{issue['path']}: {issue['message']}{details}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

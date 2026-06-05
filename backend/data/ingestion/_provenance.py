"""Extraction-rule provenance helpers."""
from __future__ import annotations

import subprocess
from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    base = Path.cwd() if start is None else Path(start).resolve()
    if base.is_file():
        base = base.parent
    output = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=base,
        text=True,
    )
    return Path(output.strip())


def extraction_rule_sha(module_file: str | Path) -> str:
    module_path = Path(module_file).resolve()
    root = repo_root(module_path)
    rel = module_path.relative_to(root)
    output = subprocess.check_output(
        ["git", "log", "-n", "1", "--pretty=%H", "--", str(rel)],
        cwd=root,
        text=True,
    ).strip()
    if not output:
        raise RuntimeError(f"no git history for extraction module: {module_path}")
    return output[:7]


def extraction_rules_for(modules: dict[str, str | Path]) -> dict[str, str]:
    return {
        name: extraction_rule_sha(path)
        for name, path in modules.items()
    }

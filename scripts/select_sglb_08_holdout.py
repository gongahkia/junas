#!/usr/bin/env python3
"""Select the SGLB-08 40-case human-review holdout."""
from __future__ import annotations

import argparse
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = (
    REPO_ROOT
    / "backend"
    / "benchmark"
    / "datasets"
    / "sglb_08_clause_tone_reviewed"
    / "dataset.yaml"
)
OUTPUT_PATH = DATASET_PATH.with_name("human_review_checklist.md")
DEFAULT_SEED = 42
DEFAULT_N = 40


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=str(DATASET_PATH), help="Reviewed SGLB-08 dataset YAML.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Markdown checklist path.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Deterministic sampling seed.")
    parser.add_argument("--n", type=int, default=DEFAULT_N, help="Holdout size.")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_path = Path(args.output)
    cases = _load_cases(dataset_path)
    selected, allocation = select_holdout(cases, n=args.n, seed=args.seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_checklist(selected, allocation, dataset_path=dataset_path, seed=args.seed),
        encoding="utf-8",
    )
    print(f"wrote {len(selected)} rows to {output_path}")
    for tone, clause_type in sorted(allocation):
        print(f"{tone}\t{clause_type}\t{allocation[(tone, clause_type)]}")
    return 0


def select_holdout(
    cases: list[dict[str, Any]],
    *,
    n: int = DEFAULT_N,
    seed: int = DEFAULT_SEED,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], int]]:
    cells: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        cells[(_tone(case), _clause_type(case))].append(case)
    for cell_cases in cells.values():
        cell_cases.sort(key=lambda item: str(item.get("name", "")))
    if n < len(cells):
        raise ValueError(f"holdout size {n} cannot cover {len(cells)} non-empty cells")

    rng = random.Random(seed)
    allocation = {cell: 1 for cell in cells}
    remaining = n - len(cells)
    total_cases = sum(len(cell_cases) for cell_cases in cells.values())
    quotas = {
        cell: remaining * len(cell_cases) / total_cases
        for cell, cell_cases in cells.items()
    }
    for cell, quota in quotas.items():
        extra = int(quota)
        allocation[cell] += extra
        remaining -= extra
    tie_breaks = {cell: rng.random() for cell in cells}
    ranked = sorted(
        cells,
        key=lambda cell: (-(quotas[cell] - int(quotas[cell])), tie_breaks[cell], cell),
    )
    for cell in ranked[:remaining]:
        allocation[cell] += 1

    selected: list[dict[str, Any]] = []
    for cell in sorted(cells):
        count = allocation[cell]
        selected.extend(sorted(rng.sample(cells[cell], count), key=lambda item: str(item.get("name", ""))))
    return selected, allocation


def render_checklist(
    selected: list[dict[str, Any]],
    allocation: dict[tuple[str, str], int],
    *,
    dataset_path: Path,
    seed: int,
) -> str:
    lines = [
        "# SGLB-08 Human Review Checklist",
        "",
        f"Dataset: `{_display_path(dataset_path)}`",
        f"Selection seed: `{seed}`",
        f"Holdout size: `{len(selected)}`",
        "",
        "Fill `human_decision` with exactly one of: `agree`, `disagree`, `unclear`.",
        "Use `notes` for the reason. Do not edit `dataset.yaml`; accepted disputes are recorded as errata.",
        "",
        "## Stratification",
        "",
        "| tone | clause_type | selected |",
        "|---|---:|---:|",
    ]
    for (tone, clause_type), count in sorted(allocation.items()):
        lines.append(f"| {_cell(tone)} | {_cell(clause_type)} | {count} |")
    lines.extend([
        "",
        "## Checklist",
        "",
        "| case_id | tone | clause_type | clause_text_excerpt | gold_label | human_decision | notes |",
        "|---|---:|---:|---|---:|---|---|",
    ])
    for case in selected:
        tone = _tone(case)
        clause_type = _clause_type(case)
        lines.append(
            "| "
            f"{_cell(str(case.get('name', '')))} | "
            f"{_cell(tone)} | "
            f"{_cell(clause_type)} | "
            f"{_cell(_excerpt(str(case.get('inputs', {}).get('clause_text', ''))))} | "
            f"{_cell(tone)} |  |  |"
        )
    lines.append("")
    return "\n".join(lines)


def _load_cases(path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = raw.get("cases", []) if isinstance(raw, dict) else []
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"no cases found in {path}")
    return cases


def _tone(case: dict[str, Any]) -> str:
    labels = case.get("expected_output", {}).get("labels", [])
    if not isinstance(labels, list) or len(labels) != 1:
        raise ValueError(f"case {case.get('name')} must have exactly one label")
    return str(labels[0]).strip()


def _clause_type(case: dict[str, Any]) -> str:
    clause_type = str(case.get("inputs", {}).get("clause_type", "")).strip()
    if clause_type:
        return clause_type
    params = case.get("metadata", {}).get("taxonomy_cell", {}).get("params", {})
    return str(params.get("clause_type", "")).strip()


def _excerpt(text: str, limit: int = 400) -> str:
    squashed = re.sub(r"\s+", " ", text).strip()
    if len(squashed) <= limit:
        return squashed
    return squashed[: limit - 3].rstrip() + "..."


def _cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())

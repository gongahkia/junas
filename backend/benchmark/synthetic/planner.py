"""Deterministic matrix expansion and provider rotation."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark.synthetic.taxonomy import DATASET_ROOT, TaxonomyCell, cells_for, task_spec

DEFAULT_PROVIDERS = ("anthropic", "openai", "google")
ESTIMATED_COST_PER_EXAMPLE_USD = {
    "anthropic": 0.025,
    "openai": 0.015,
    "azure": 0.015,  # Azure OpenAI matches OpenAI list pricing per-model
    "google": 0.01,
    "gemini": 0.01,
    "mock": 0.0,
}


@dataclass(frozen=True)
class PlanItem:
    task: str
    index: int
    slug: str
    provider: str
    cell: TaxonomyCell
    candidate_path: Path
    estimated_cost_usd: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "index": self.index,
            "slug": self.slug,
            "provider": self.provider,
            "taxonomy_cell": self.cell.as_metadata(),
            "candidate_path": str(self.candidate_path),
            "estimated_cost_usd": self.estimated_cost_usd,
        }


def parse_providers(raw: str | tuple[str, ...] | list[str]) -> tuple[str, ...]:
    if isinstance(raw, str):
        providers = tuple(part.strip().lower() for part in raw.split(",") if part.strip())
    else:
        providers = tuple(str(part).strip().lower() for part in raw if str(part).strip())
    if not providers:
        raise ValueError("at least one provider is required")
    allowed = set(ESTIMATED_COST_PER_EXAMPLE_USD)
    invalid = sorted(set(providers) - allowed)
    if invalid:
        raise ValueError(f"unknown providers: {invalid}")
    return providers


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return re.sub(r"_+", "_", cleaned)


def _candidate_dir(task: str, base_dir: Path | None) -> Path:
    spec = task_spec(task)
    root = base_dir or DATASET_ROOT
    return root / spec.candidate_dir_name


def _slug_for(task: str, cell: TaxonomyCell, sequence: int) -> str:
    return f"{task}_{_slugify(cell.cell_id)}_{sequence:03d}"


def build_plan(
    *,
    task: str,
    n: int,
    providers: str | tuple[str, ...] | list[str] = DEFAULT_PROVIDERS,
    seed: int = 0,
    base_dir: Path | None = None,
) -> list[PlanItem]:
    if n < 0:
        raise ValueError("n must be >= 0")
    provider_list = parse_providers(providers)
    cells = cells_for(task)
    rng = random.Random(seed)
    shuffled = list(cells)
    rng.shuffle(shuffled)

    candidate_dir = _candidate_dir(task, base_dir)
    items: list[PlanItem] = []
    for idx in range(n):
        cell = shuffled[idx % len(shuffled)]
        provider = provider_list[idx % len(provider_list)]
        slug = _slug_for(task, cell, idx + 1)
        items.append(
            PlanItem(
                task=task,
                index=idx,
                slug=slug,
                provider=provider,
                cell=cell,
                candidate_path=candidate_dir / f"{slug}.yaml",
                estimated_cost_usd=ESTIMATED_COST_PER_EXAMPLE_USD[provider],
            )
        )
    return items


def estimate_cost_usd(plan: list[PlanItem]) -> float:
    return round(sum(item.estimated_cost_usd for item in plan), 6)

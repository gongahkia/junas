"""Taxonomy cells for synthesis-approved SG-LegalBench tasks.

Only SGLB-08, SGLB-12, and SGLB-15 may use synthetic examples. The label for
each generated case is encoded in the taxonomy cell and copied directly into
``expected_output``; no LLM labeling step is allowed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.services.clause_service import CLAUSE_LIBRARY
from api.services.template_service import TEMPLATES
from benchmark.synthetic.sglb_08 import load_tone_taxonomy
from benchmark.synthetic.sglb_12 import load_issue_compositions
from benchmark.synthetic.sglb_15 import load_constraint_taxonomy

DATASET_ROOT = Path(__file__).resolve().parents[1] / "datasets"
GENERATOR_VERSION = "sglb-synthetic-generator-v1"
PROMPT_VERSION = "sglb-synthetic-prompts-v1"
VARIANTS = ("default", "adversarial", "negative")


@dataclass(frozen=True)
class SyntheticTaskSpec:
    task: str
    display_name: str
    candidate_dir_name: str
    reviewed_dir_name: str
    evaluator: str

    @property
    def candidate_dir(self) -> Path:
        return DATASET_ROOT / self.candidate_dir_name

    @property
    def reviewed_dir(self) -> Path:
        return DATASET_ROOT / self.reviewed_dir_name


@dataclass(frozen=True)
class TaxonomyCell:
    task: str
    cell_id: str
    label: dict[str, Any]
    params: dict[str, Any]
    variant: str

    def as_metadata(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "cell_id": self.cell_id,
            "variant": self.variant,
            "label": self.label,
            "params": self.params,
        }


SYNTHETIC_TASKS: dict[str, SyntheticTaskSpec] = {
    "sglb_08": SyntheticTaskSpec(
        task="sglb_08",
        display_name="SGLB-08 Clause-Tone",
        candidate_dir_name="sglb_08_clause_tone_candidates",
        reviewed_dir_name="sglb_08_clause_tone_reviewed",
        evaluator="multi_label_f1",
    ),
    "sglb_12": SyntheticTaskSpec(
        task="sglb_12",
        display_name="SGLB-12 Multi-Issue-Spotting",
        candidate_dir_name="sglb_12_multi_issue_candidates",
        reviewed_dir_name="sglb_12_multi_issue_reviewed",
        evaluator="multi_label_f1",
    ),
    "sglb_15": SyntheticTaskSpec(
        task="sglb_15",
        display_name="SGLB-15 Draft-Constraint-Sat",
        candidate_dir_name="sglb_15_draft_constraints_candidates",
        reviewed_dir_name="sglb_15_draft_constraints_reviewed",
        evaluator="constraint_sat",
    ),
}


def _sglb_08_cells() -> list[TaxonomyCell]:
    taxonomy = load_tone_taxonomy()
    cells: list[TaxonomyCell] = []
    for clause in CLAUSE_LIBRARY:
        for tone in taxonomy.tones:
            for variant in VARIANTS:
                cells.append(
                    TaxonomyCell(
                        task="sglb_08",
                        cell_id=f"{clause.id}_{tone.id}_{variant}",
                        label={"labels": [tone.id]},
                        params={
                            "clause_id": clause.id,
                            "clause_type": clause.name,
                            "category": clause.category,
                            "tone": tone.id,
                            "tone_context": tone.as_prompt_context(),
                            "tone_taxonomy_version": taxonomy.version,
                            "source_note": clause.notes,
                        },
                        variant=variant,
                    )
                )
    return cells


def _sglb_12_cells() -> list[TaxonomyCell]:
    matrix = load_issue_compositions()
    cells: list[TaxonomyCell] = []
    for composition in matrix.compositions:
        labels = list(composition.labels)
        for variant in VARIANTS:
            cells.append(
                TaxonomyCell(
                    task="sglb_12",
                    cell_id=f"{composition.id}_{variant}",
                    label={"labels": labels},
                    params={
                        "issues": labels,
                        "issue_count": len(labels),
                        "sources": list(composition.sources),
                        "issue_context": composition.as_prompt_context()["issues"],
                        "composition_id": composition.id,
                        "composition_context": composition.as_prompt_context(),
                        "composition_version": matrix.version,
                    },
                    variant=variant,
                )
            )
    return cells


def _sglb_15_cells() -> list[TaxonomyCell]:
    taxonomy = load_constraint_taxonomy()
    cells: list[TaxonomyCell] = []
    for template in TEMPLATES:
        for constraint_set in taxonomy.applicable_sets(template.id):
            for variant in VARIANTS:
                constraints = constraint_set.constraint_payload()
                cells.append(
                    TaxonomyCell(
                        task="sglb_15",
                        cell_id=f"{template.id}_{constraint_set.id}_{variant}",
                        label={"constraints": constraints},
                        params={
                            "template_id": template.id,
                            "template_title": template.title,
                            "template_category": template.category,
                            "constraints": constraints,
                            "constraint_set_id": constraint_set.id,
                            "constraint_taxonomy_version": taxonomy.version,
                            "constraint_context": constraint_set.as_prompt_context(),
                        },
                        variant=variant,
                    )
                )
    return cells


def supported_tasks() -> tuple[str, ...]:
    return tuple(SYNTHETIC_TASKS)


def task_spec(task: str) -> SyntheticTaskSpec:
    try:
        return SYNTHETIC_TASKS[task]
    except KeyError as exc:
        allowed = ", ".join(sorted(SYNTHETIC_TASKS))
        raise ValueError(f"synthetic generation is only available for: {allowed}") from exc


def cells_for(task: str) -> list[TaxonomyCell]:
    task_spec(task)
    if task == "sglb_08":
        return _sglb_08_cells()
    if task == "sglb_12":
        return _sglb_12_cells()
    if task == "sglb_15":
        return _sglb_15_cells()
    raise AssertionError(f"unhandled synthetic task: {task}")

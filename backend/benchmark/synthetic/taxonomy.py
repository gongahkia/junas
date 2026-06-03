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
from benchmark.constraints import CONSTRAINTS

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


ISSUE_GROUPS: tuple[tuple[str, ...], ...] = (
    ("pdpa.protection_obligation", "ea.notice_period_breach"),
    ("pdpa.consent_obligation", "roc.service_of_originating_process"),
    ("pdpa.notification_obligation", "ea.salary_payment_breach", "roc.affidavit_evidence_defect"),
    ("pdpa.retention_limitation", "ea.overtime_pay_breach"),
    ("pdpa.access_correction_obligation", "roc.expert_evidence_procedure_breach"),
    (
        "pdpa.protection_obligation",
        "ea.public_holiday_pay_breach",
        "roc.pleadings_particulars_defect",
    ),
    (
        "pdpa.consent_obligation",
        "pdpa.notification_obligation",
        "ea.notice_period_breach",
        "roc.service_of_originating_process",
    ),
    (
        "pdpa.retention_limitation",
        "ea.salary_payment_breach",
        "roc.expert_evidence_procedure_breach",
    ),
)


def _sglb_08_cells() -> list[TaxonomyCell]:
    cells: list[TaxonomyCell] = []
    for clause in CLAUSE_LIBRARY:
        for tone in ("standard", "aggressive", "balanced", "protective"):
            for variant in VARIANTS:
                cells.append(
                    TaxonomyCell(
                        task="sglb_08",
                        cell_id=f"{clause.id}_{tone}_{variant}",
                        label={"labels": [tone]},
                        params={
                            "clause_id": clause.id,
                            "clause_type": clause.name,
                            "category": clause.category,
                            "tone": tone,
                            "source_note": clause.notes,
                        },
                        variant=variant,
                    )
                )
    return cells


def _sglb_12_cells() -> list[TaxonomyCell]:
    cells: list[TaxonomyCell] = []
    for idx, issues in enumerate(ISSUE_GROUPS, start=1):
        for variant in VARIANTS:
            cells.append(
                TaxonomyCell(
                    task="sglb_12",
                    cell_id=f"compound_{idx:02d}_{variant}",
                    label={"labels": list(issues)},
                    params={
                        "issues": list(issues),
                        "issue_count": len(issues),
                        "sources": sorted({issue.split(".", 1)[0] for issue in issues}),
                    },
                    variant=variant,
                )
            )
    return cells


def _constraint_sets() -> tuple[tuple[dict[str, Any], ...], ...]:
    return (
        (
            {"id": "party", "kind": "named_party_present", "params": {"party_names": ["Acme Pte Ltd", "Beacon Pte Ltd"]}},
            {"id": "law", "kind": "governing_law_singapore", "params": {}},
            {"id": "date", "kind": "iso_date_present", "params": {}},
        ),
        (
            {"id": "section", "kind": "required_section_present", "params": {"heading": "Confidentiality", "min_words": 40}},
            {"id": "amount", "kind": "sgd_amount_present", "params": {}},
            {"id": "forbidden", "kind": "no_forbidden_phrase", "params": {"phrases": ["best efforts"]}},
        ),
        (
            {"id": "party", "kind": "named_party_present", "params": {"party_names": ["Delta Pte Ltd"]}},
            {"id": "words", "kind": "min_word_count", "params": {"min_words": 120}},
            {"id": "law", "kind": "governing_law_singapore", "params": {}},
            {"id": "amount", "kind": "sgd_amount_present", "params": {}},
        ),
    )


def _validate_constraint_sets() -> None:
    missing = {
        constraint["kind"]
        for group in _constraint_sets()
        for constraint in group
        if constraint["kind"] not in CONSTRAINTS
    }
    if missing:
        raise RuntimeError(f"synthetic taxonomy references unknown constraints: {sorted(missing)}")


def _sglb_15_cells() -> list[TaxonomyCell]:
    _validate_constraint_sets()
    cells: list[TaxonomyCell] = []
    for template in TEMPLATES:
        for set_idx, constraints in enumerate(_constraint_sets(), start=1):
            for variant in VARIANTS:
                cells.append(
                    TaxonomyCell(
                        task="sglb_15",
                        cell_id=f"{template.id}_constraints_{set_idx}_{variant}",
                        label={"constraints": [dict(item) for item in constraints]},
                        params={
                            "template_id": template.id,
                            "template_title": template.title,
                            "template_category": template.category,
                            "constraints": [dict(item) for item in constraints],
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

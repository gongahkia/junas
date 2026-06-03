"""Task-specific quality checks for synthetic generated examples."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from benchmark.constraints import CONSTRAINTS
from benchmark.synthetic.sglb_08 import load_tone_taxonomy
from benchmark.synthetic.sglb_12 import load_issue_compositions, load_issue_taxonomy
from benchmark.synthetic.sglb_15 import load_constraint_taxonomy

PROMPT_LEAKAGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bGold (?:label|issue|constraint) payload\b", re.IGNORECASE),
    re.compile(r"\bPrompt parameters\b", re.IGNORECASE),
    re.compile(r"\bVariant instruction\b", re.IGNORECASE),
    re.compile(r"\bReturn only\b", re.IGNORECASE),
    re.compile(r"\bexpected_output\b", re.IGNORECASE),
    re.compile(r"\btaxonomy_cell\b", re.IGNORECASE),
    re.compile(r"```"),
)

REFUSAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bas an ai\b", re.IGNORECASE),
    re.compile(r"\bi (?:cannot|can't|am unable to)\b", re.IGNORECASE),
    re.compile(r"\bnot legal advice\b", re.IGNORECASE),
)

ISSUE_LABEL_RE = re.compile(r"\b(?:pdpa|ea|roc)\.[a-z0-9_]+\b", re.IGNORECASE)


@dataclass
class QualityReport:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "metrics": self.metrics,
        }


def _body_for_case(case: dict[str, Any]) -> str:
    inputs = case.get("inputs") or {}
    for key in ("clause_text", "scenario", "drafting_brief"):
        if key in inputs:
            return str(inputs[key])
    return ""


def check_case_quality(case: dict[str, Any]) -> QualityReport:
    task = str((case.get("metadata") or {}).get("sglb_task") or "")
    body = _body_for_case(case)
    report = QualityReport()
    words = body.split()
    report.metrics["word_count"] = len(words)
    report.metrics["char_count"] = len(body)

    if not body.strip():
        report.add_error("body is empty")
        return report
    for pattern in PROMPT_LEAKAGE_PATTERNS:
        if pattern.search(body):
            report.add_error(f"prompt leakage detected: {pattern.pattern}")
    for pattern in REFUSAL_PATTERNS:
        if pattern.search(body):
            report.add_error(f"refusal/disclaimer text detected: {pattern.pattern}")

    if task == "sglb_08":
        _check_sglb_08(case, body, report)
    elif task == "sglb_12":
        _check_sglb_12(case, body, report)
    elif task == "sglb_15":
        _check_sglb_15(case, body, report)
    else:
        report.add_error(f"unsupported synthetic task for quality checks: {task}")
    return report


def _check_sglb_08(case: dict[str, Any], body: str, report: QualityReport) -> None:
    labels = [str(label) for label in (case.get("expected_output") or {}).get("labels") or []]
    taxonomy = load_tone_taxonomy()
    metadata = case.get("metadata") or {}
    taxonomy_cell = metadata.get("taxonomy_cell") or {}
    params = taxonomy_cell.get("params") or {}
    tone = str(labels[0]) if labels else ""
    declared_tone = str(params.get("tone") or "")
    if len(labels) != 1:
        report.add_error("SGLB-08 must have exactly one tone label")
    elif tone not in taxonomy.id_set:
        report.add_error(f"SGLB-08 tone label is not in taxonomy: {tone}")
    if not declared_tone:
        report.add_error("SGLB-08 taxonomy metadata is missing tone")
    else:
        try:
            taxonomy.require_valid(declared_tone)
            if tone and tone != declared_tone:
                report.add_error("SGLB-08 tone label does not match declared tone metadata")
        except ValueError as exc:
            report.add_error(str(exc))
    if params.get("tone_taxonomy_version") != taxonomy.version:
        report.add_error("SGLB-08 tone taxonomy version is missing or stale")
    if report.metrics["word_count"] < 80:
        report.add_warning("SGLB-08 clause is shorter than the target range")
    if report.metrics["word_count"] > 260:
        report.add_warning("SGLB-08 clause is longer than the target range")
    if tone and re.search(rf"\b{re.escape(tone)}\b", body, re.IGNORECASE):
        report.add_warning("SGLB-08 body mentions the target tone label verbatim")


def _check_sglb_12(case: dict[str, Any], body: str, report: QualityReport) -> None:
    labels = [str(label) for label in (case.get("expected_output") or {}).get("labels") or []]
    taxonomy = load_issue_taxonomy()
    matrix = load_issue_compositions()
    metadata = case.get("metadata") or {}
    taxonomy_cell = metadata.get("taxonomy_cell") or {}
    params = taxonomy_cell.get("params") or {}
    composition_id = str(params.get("composition_id") or "")
    if len(labels) < 2:
        report.add_error("SGLB-12 must have at least two issue labels")
    if len(labels) > 4:
        report.add_error("SGLB-12 must not exceed four issue labels")
    invalid = sorted(set(labels) - taxonomy.code_set)
    if invalid:
        report.add_error(f"SGLB-12 labels are not in taxonomy: {invalid}")
    if not composition_id:
        report.add_error("SGLB-12 taxonomy metadata is missing composition_id")
    else:
        try:
            composition = matrix.require_valid(composition_id)
            if tuple(labels) != composition.labels:
                report.add_error("SGLB-12 labels do not match the declared issue composition")
        except ValueError as exc:
            report.add_error(str(exc))
    if params.get("composition_version") != matrix.version:
        report.add_error("SGLB-12 composition matrix version is missing or stale")
    leaked_labels = sorted(set(match.group(0).lower() for match in ISSUE_LABEL_RE.finditer(body)))
    if leaked_labels:
        report.add_error(f"SGLB-12 body leaks machine-readable issue labels: {leaked_labels}")
    if report.metrics["word_count"] < 250:
        report.add_warning("SGLB-12 scenario is shorter than the target range")
    if report.metrics["word_count"] > 950:
        report.add_warning("SGLB-12 scenario is longer than the target range")


def _check_sglb_15(case: dict[str, Any], body: str, report: QualityReport) -> None:
    constraints = (case.get("expected_output") or {}).get("constraints") or []
    input_constraints = (case.get("inputs") or {}).get("constraints") or []
    metadata = case.get("metadata") or {}
    taxonomy_cell = metadata.get("taxonomy_cell") or {}
    params = taxonomy_cell.get("params") or {}
    template_id = str(params.get("template_id") or "")
    constraint_set_id = str(params.get("constraint_set_id") or "")
    taxonomy = load_constraint_taxonomy()
    if constraints != input_constraints:
        report.add_error("SGLB-15 expected_output constraints differ from input constraints")
    if not template_id:
        report.add_error("SGLB-15 taxonomy metadata is missing template_id")
    if not constraint_set_id:
        report.add_error("SGLB-15 taxonomy metadata is missing constraint_set_id")
    if template_id and constraint_set_id:
        try:
            constraint_set = taxonomy.require_valid_set_for_template(constraint_set_id, template_id)
            if constraints != constraint_set.constraint_payload():
                report.add_error("SGLB-15 constraints do not match the declared constraint set")
        except ValueError as exc:
            report.add_error(str(exc))
    if params.get("constraint_taxonomy_version") != taxonomy.version:
        report.add_error("SGLB-15 constraint taxonomy version is missing or stale")
    for constraint in constraints:
        kind = constraint.get("kind")
        if kind not in CONSTRAINTS:
            report.add_error(f"SGLB-15 unknown constraint kind: {kind}")
    if report.metrics["word_count"] < 80:
        report.add_warning("SGLB-15 brief is shorter than the target range")
    if report.metrics["word_count"] > 320:
        report.add_warning("SGLB-15 brief is longer than the target range")
    if re.search(r"^#\s+", body, re.MULTILINE):
        report.add_warning("SGLB-15 body looks like a drafted document rather than a drafting brief")

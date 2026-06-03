"""Task-specific quality checks for synthetic generated examples."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from benchmark.constraints import CONSTRAINTS

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
    labels = (case.get("expected_output") or {}).get("labels") or []
    if len(labels) != 1:
        report.add_error("SGLB-08 must have exactly one tone label")
    if report.metrics["word_count"] < 80:
        report.add_warning("SGLB-08 clause is shorter than the target range")
    if report.metrics["word_count"] > 260:
        report.add_warning("SGLB-08 clause is longer than the target range")
    tone = str(labels[0]) if labels else ""
    if tone and re.search(rf"\b{re.escape(tone)}\b", body, re.IGNORECASE):
        report.add_warning("SGLB-08 body mentions the target tone label verbatim")


def _check_sglb_12(case: dict[str, Any], body: str, report: QualityReport) -> None:
    labels = [str(label) for label in (case.get("expected_output") or {}).get("labels") or []]
    if len(labels) < 2:
        report.add_error("SGLB-12 must have at least two issue labels")
    if len(labels) > 4:
        report.add_error("SGLB-12 must not exceed four issue labels")
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
    if constraints != input_constraints:
        report.add_error("SGLB-15 expected_output constraints differ from input constraints")
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

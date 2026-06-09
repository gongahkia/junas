"""LLM-tier inverse audit: "what did we miss?"

Sends a structured summary of the deterministic findings + a SHA-256 hash of the
document body to an LLM auditor. The auditor returns advisory warnings about
potentially-missed patterns. Each warning is journaled as a `coverage_warning`
event under the review session and surfaced in `ReviewResult.coverage_warnings`.

Privacy posture:
- The auditor receives `rule`, `severity`, and `reason` for each finding — these are
  already public-by-virtue-of-being-detected.
- The auditor does NOT receive `matched_text`, `start_char`, or `end_char` — those
  are the sensitive spans and stay inside the process boundary.
- The auditor receives a SHA-256 hash of the document text only as a proof-of-doc
  reference (so the journaled warning can be cross-referenced with the review's
  text_hash).

Output discipline:
- Warnings remain journaled as `coverage_warning` events. Under `audit_grade`, the
  review engine also promotes normalized LLM warnings into capped-severity
  `llm_raised_finding` entries for reviewer adjudication.
- The auditor cannot assign high severity; the engine clamps LLM-origin findings to
  deterministic-medium or lower.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol


class LLMCoverageAuditor(Protocol):
    """Minimal contract for the LLM inverse-audit helper."""

    def audit(
        self,
        *,
        findings: list[dict[str, Any]],
        body_hash: str,
        document_type: str,
    ) -> list[dict[str, Any]]:
        """Return a list of advisory warnings about possibly-missed patterns.
        Each warning should carry at minimum:
            rule_guess: str    — rule name that may be under-covered
            why: str           — one-line reason
            confidence: float  — auditor's self-reported confidence in [0, 1]
        Implementations may add extra fields; they pass through to the journal opaquely.
        Implementations MUST return [] on failure (no exception)."""
        ...


def _summarize_for_audit(findings: list) -> list[dict[str, Any]]:
    """Strip findings down to fields the LLM auditor needs. Excludes matched_text
    and span offsets — those stay inside the process boundary."""
    summary: list[dict[str, Any]] = []
    for finding in findings:
        summary.append({
            "rule": finding.rule,
            "category": finding.category,
            "severity": finding.severity,
            "jurisdiction": finding.jurisdiction,
            "reason": finding.reason,
        })
    return summary


def compute_body_hash(text: str) -> str:
    """SHA-256 of the document body. Cross-reference identifier for journal entries."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_coverage_audit(
    *,
    text: str,
    findings: list,
    document_type: str,
    auditor: LLMCoverageAuditor,
    fail_closed: bool = False,
) -> list[dict[str, Any]]:
    """Call the auditor with a privacy-safe summary; return the list of warnings.
    Catches auditor failures and returns [] unless fail_closed is set."""
    body_hash = compute_body_hash(text)
    summary = _summarize_for_audit(findings)
    try:
        warnings = auditor.audit(
            findings=summary, body_hash=body_hash, document_type=document_type,
        )
    except Exception as exc:
        if fail_closed:
            raise RuntimeError(f"coverage auditor failed: {exc}") from exc
        return []
    if warnings is None:
        warnings = []
    if not isinstance(warnings, list):
        if fail_closed:
            raise RuntimeError("coverage auditor returned non-list output")
        return []
    # normalize: each warning must be a dict with at least rule_guess + why fields
    normalized: list[dict[str, Any]] = []
    for index, warning in enumerate(warnings):
        if not isinstance(warning, dict):
            if fail_closed:
                raise RuntimeError(f"coverage auditor warning {index} is not an object")
            continue
        if "rule_guess" not in warning or "why" not in warning:
            if fail_closed:
                raise RuntimeError(
                    f"coverage auditor warning {index} missing rule_guess or why"
                )
            continue
        item = dict(warning)
        item["body_hash"] = body_hash
        normalized.append(item)
    return normalized

"""Review-decision state machine backed by the append-only journal.

Decisions are not stored in a separate database. Every state mutation is an event in
`journal.jsonl`, so the audit trail is the source of truth. Replaying events from genesis
reconstructs the current state of any review session.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any

from junas.review.journal import JournalEntry, append_event, read_journal

DECISION_ACTIONS = (
    "accept",
    "reject",
    "rewrite",
    "approve",
    "policy_exception",
    "accept_risk",
    "request_changes",
    "hold",
)
DECISION_TAXONOMY = (
    "false_positive",
    "false_negative",
    "acceptable_risk",
    "public_source_confirmed",
    "stale_information",
    "policy_exception",
)
ALLOWED_ACTIONS = frozenset(DECISION_ACTIONS)
ALLOWED_DECISION_TAXONOMY = frozenset(DECISION_TAXONOMY)
REJECT_ACTIONS = frozenset({"reject"})
AUTHORIZED_REVIEWER_IDENTITY_SOURCES = frozenset({"api_key", "jwt", "dev_header"})
TEXT_BEARING_DETECTOR_FEEDBACK_KEYS = frozenset(
    {
        "raw_text",
        "matched_text",
        "document_text",
        "email_body",
        "prompt",
        "source_excerpt",
        "recipient_address",
        "filename",
        "mapping_value",
        "auth_header",
        "local_pairing_token",
    }
)
POSITIVE_CORPUS_ACTIONS = frozenset(
    {
        "accept",
        "rewrite",
        "approve",
        "policy_exception",
        "accept_risk",
        "request_changes",
        "hold",
    }
)

EVENT_REVIEW_STARTED = "review_started"
EVENT_DECISION_RECORDED = "decision_recorded"
EVENT_ANONYMIZE_APPLIED = "anonymize_applied"
EVENT_AUDIT_EXPORTED = "audit_exported"
EVENT_COVERAGE_WARNING = "coverage_warning"  # advisory output from the LLM inverse audit
EVENT_POLICY_DECISION_RECORDED = "policy_decision_recorded"
EVENT_SUBJECT_ERASURE_RECORDED = "subject_erasure_recorded"
EVENT_APPROVAL_REQUESTED = "approval_requested"
REVIEW_PERSIST_SPANS_ENV = "JUNAS_REVIEW_PERSIST_SPANS"


class ReviewSessionError(ValueError):
    """Raised when a session cannot be located or a decision is invalid."""


def normalize_decision_taxonomy(value: str) -> str:
    taxonomy = value.strip()
    if taxonomy not in ALLOWED_DECISION_TAXONOMY:
        raise ReviewSessionError(f"decision_taxonomy must be one of {sorted(ALLOWED_DECISION_TAXONOMY)}; got '{value}'")
    return taxonomy


def _normalize_reviewer_confidence(value: float | None) -> float | None:
    if value is None:
        return None
    if value < 0.0 or value > 1.0:
        raise ReviewSessionError("reviewer_confidence must be between 0.0 and 1.0")
    return float(value)


def _normalize_detector_feedback(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    blocked = sorted(TEXT_BEARING_DETECTOR_FEEDBACK_KEYS.intersection(str(key).strip().lower() for key in value))
    if blocked:
        raise ReviewSessionError(f"detector_feedback must not include raw text fields: {', '.join(blocked)}")
    return dict(value)


@dataclass(frozen=True)
class Decision:
    finding_id: str
    action: str
    replacement_text: str = ""
    rationale: str = ""
    reviewer_id: str = ""  # who recorded this decision; auth principal for new production entries
    reviewer_identity_source: str = "none"  # jwt | api_key | dev_header | none | legacy
    decision_taxonomy: str = ""
    reviewer_confidence: float | None = None
    detector_feedback: dict[str, Any] = field(default_factory=dict)


def _dedupe_preserve_order(values: list[str] | tuple[str, ...]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def _is_authorized_reviewer_decision(decision: dict[str, Any]) -> bool:
    source = str(decision.get("reviewer_identity_source") or "").strip().lower()
    reviewer_id = str(decision.get("reviewer_id") or "").strip()
    return source in AUTHORIZED_REVIEWER_IDENTITY_SOURCES and bool(reviewer_id)


def _is_authorized_reject(decision: dict[str, Any]) -> bool:
    return str(decision.get("action") or "") in REJECT_ACTIONS and _is_authorized_reviewer_decision(decision)


def _is_truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _sanitize_journal_finding(finding: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(finding)
    matched_text = str(sanitized.get("matched_text", "") or "")
    if matched_text:
        sanitized["matched_text_sha256"] = hashlib.sha256(matched_text.encode("utf-8")).hexdigest()
        sanitized["matched_text_char_count"] = len(matched_text)
    if not _is_truthy_env(REVIEW_PERSIST_SPANS_ENV):
        sanitized.pop("matched_text", None)
    return sanitized


def start_review_session(
    *,
    review_id: str,
    text_hash: str,
    document_type: str,
    source_jurisdiction: str,
    destination_jurisdiction: str,
    findings: list[dict[str, Any]],
    tenant_id: str | None = None,
) -> JournalEntry:
    journal_findings = [_sanitize_journal_finding(finding) for finding in findings]
    return append_event(
        event_type=EVENT_REVIEW_STARTED,
        review_id=review_id,
        payload={
            "text_hash": text_hash,
            "document_type": document_type,
            "source_jurisdiction": source_jurisdiction,
            "destination_jurisdiction": destination_jurisdiction,
            "findings": journal_findings,
        },
        tenant_id=tenant_id,
    )


def record_decision(*, review_id: str, decision: Decision, tenant_id: str | None = None) -> dict[str, Any]:
    if decision.action not in ALLOWED_ACTIONS:
        raise ReviewSessionError(f"action must be one of {sorted(ALLOWED_ACTIONS)}; got '{decision.action}'")
    decision_taxonomy = normalize_decision_taxonomy(decision.decision_taxonomy) if decision.decision_taxonomy else ""
    reviewer_confidence = _normalize_reviewer_confidence(decision.reviewer_confidence)
    detector_feedback = _normalize_detector_feedback(decision.detector_feedback)

    session = read_journal(review_id=review_id, tenant_id=tenant_id)
    if not session or session[0].event_type != EVENT_REVIEW_STARTED:
        raise ReviewSessionError(f"unknown review_id: {review_id}")

    findings = session[0].payload.get("findings", [])
    if not any(f.get("id") == decision.finding_id for f in findings):
        raise ReviewSessionError(f"unknown finding_id: {decision.finding_id}")

    payload = {
        "finding_id": decision.finding_id,
        "action": decision.action,
        "replacement_text": decision.replacement_text,
        "rationale": decision.rationale,
        "reviewer_id": decision.reviewer_id,
        "reviewer_identity_source": decision.reviewer_identity_source,
    }
    if decision_taxonomy:
        payload["decision_taxonomy"] = decision_taxonomy
    if reviewer_confidence is not None:
        payload["reviewer_confidence"] = reviewer_confidence
    if detector_feedback:
        payload["detector_feedback"] = detector_feedback

    entry = append_event(
        event_type=EVENT_DECISION_RECORDED,
        review_id=review_id,
        payload=payload,
        tenant_id=tenant_id,
    )
    return {
        "review_id": review_id,
        "finding_id": decision.finding_id,
        "action": decision.action,
        "decision_taxonomy": decision_taxonomy or None,
        "reviewer_confidence": reviewer_confidence,
        "detector_feedback": detector_feedback or None,
        "reviewer_id": decision.reviewer_id,
        "reviewer_identity_source": decision.reviewer_identity_source,
        "seq": entry.seq,
        "ts": entry.ts,
        "hmac": entry.hmac,
    }


def record_approval_request(
    *,
    review_id: str,
    finding_ids: list[str] | None,
    required_reviewer_roles: list[str],
    required_policy_actor_roles: list[str],
    reason_code: str,
    requester_id: str = "",
    requester_identity_source: str = "none",
    tenant_id: str | None = None,
) -> dict[str, Any]:
    session = read_journal(review_id=review_id, tenant_id=tenant_id)
    if not session or session[0].event_type != EVENT_REVIEW_STARTED:
        raise ReviewSessionError(f"unknown review_id: {review_id}")

    findings = session[0].payload.get("findings", [])
    available_ids = [str(f.get("id", "")) for f in findings if str(f.get("id", ""))]
    target_ids = _dedupe_preserve_order(finding_ids or available_ids)
    if not target_ids:
        raise ReviewSessionError("request_approval requires at least one finding_id")
    unknown_ids = sorted(set(target_ids) - set(available_ids))
    if unknown_ids:
        raise ReviewSessionError(f"unknown finding_id: {unknown_ids[0]}")

    payload = {
        "approval_status": "pending",
        "requested_action": "request_approval",
        "finding_ids": target_ids,
        "required_reviewer_roles": list(required_reviewer_roles),
        "required_policy_actor_roles": list(required_policy_actor_roles),
        "reason_code": reason_code,
        "requester_id": requester_id,
        "requester_identity_source": requester_identity_source,
    }
    entry = append_event(
        event_type=EVENT_APPROVAL_REQUESTED,
        review_id=review_id,
        payload=payload,
        tenant_id=tenant_id,
    )
    return {
        "review_id": review_id,
        "approval_status": "pending",
        "requested_action": "request_approval",
        "requested_finding_ids": target_ids,
        "required_reviewer_roles": list(required_reviewer_roles),
        "required_policy_actor_roles": list(required_policy_actor_roles),
        "reason_code": reason_code,
        "requester_id": requester_id,
        "requester_identity_source": requester_identity_source,
        "seq": entry.seq,
        "ts": entry.ts,
        "hmac": entry.hmac,
    }


def record_subject_erasure(
    *,
    review_id: str,
    pii_hash: str,
    citation: str,
    document_hash: str = "",
    finding_ids: list[str] | None = None,
    rules: list[str] | None = None,
    tenant_id: str | None = None,
) -> JournalEntry:
    return append_event(
        event_type=EVENT_SUBJECT_ERASURE_RECORDED,
        review_id=review_id,
        payload={
            "pii_hash": pii_hash,
            "citation": citation,
            "document_hash": document_hash,
            "finding_ids": sorted(set(finding_ids or [])),
            "rules": sorted(set(rules or [])),
        },
        tenant_id=tenant_id,
    )


def get_session_state(*, review_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
    entries = read_journal(review_id=review_id, tenant_id=tenant_id)
    if not entries or entries[0].event_type != EVENT_REVIEW_STARTED:
        return None
    init = entries[0].payload
    decisions: dict[str, dict[str, Any]] = {}
    audit_exports: list[dict[str, Any]] = []
    anonymize_events: list[dict[str, Any]] = []
    policy_decision_events: list[dict[str, Any]] = []
    approval_request_events: list[dict[str, Any]] = []
    for entry in entries[1:]:
        if entry.event_type == EVENT_DECISION_RECORDED:
            decisions[entry.payload["finding_id"]] = {**entry.payload, "seq": entry.seq, "ts": entry.ts}
        elif entry.event_type == EVENT_ANONYMIZE_APPLIED:
            anonymize_events.append({**entry.payload, "seq": entry.seq, "ts": entry.ts})
        elif entry.event_type == EVENT_AUDIT_EXPORTED:
            audit_exports.append({**entry.payload, "seq": entry.seq, "ts": entry.ts})
        elif entry.event_type == EVENT_POLICY_DECISION_RECORDED:
            policy_decision_events.append({**entry.payload, "seq": entry.seq, "ts": entry.ts})
        elif entry.event_type == EVENT_APPROVAL_REQUESTED:
            approval_request_events.append({**entry.payload, "seq": entry.seq, "ts": entry.ts})
    return {
        "review_id": review_id,
        "text_hash": init.get("text_hash"),
        "document_type": init.get("document_type"),
        "source_jurisdiction": init.get("source_jurisdiction"),
        "destination_jurisdiction": init.get("destination_jurisdiction"),
        "findings": init.get("findings", []),
        "decisions": list(decisions.values()),
        "anonymize_events": anonymize_events,
        "audit_exports": audit_exports,
        "policy_decisions": policy_decision_events,
        "approval_requests": approval_request_events,
    }


def findings_after_decisions(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return findings retained after reviewer decisions; only authorized reject removes a finding."""
    decisions_by_id = {d["finding_id"]: d for d in state.get("decisions", [])}
    kept: list[dict[str, Any]] = []
    for finding in state.get("findings", []):
        decision = decisions_by_id.get(finding.get("id"))
        if decision is None:
            # un-decided findings default to accepted so anonymisation is safe by default
            kept.append(finding)
            continue
        if _is_authorized_reject(decision):
            continue
        kept.append(finding)
    return kept

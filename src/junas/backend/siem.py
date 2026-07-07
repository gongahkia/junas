"""SIEM-safe event export helpers.

The exporter is intentionally low fidelity for sensitive fields. It emits enough
metadata for audit correlation while hashing or summarising fields that can carry
document text, reviewer notes, mapping originals, public-evidence queries, or finding
matches.
"""

from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
import socket
import time
from collections.abc import Callable, Mapping
from typing import Any

SCHEMA_VERSION = "junas.siem.v1"
MAX_DETAIL_STRING_CHARS = 256
_logger = logging.getLogger("junas.siem")

SENSITIVE_HASH_KEYS = {
    "anonymized_text",
    "attachment_filename",
    "base_url",
    "body",
    "comment",
    "context_after",
    "context_before",
    "document_text",
    "email_body",
    "endpoint_url",
    "error",
    "file_path",
    "jwt",
    "local_path",
    "matched_text",
    "message",
    "matter_name",
    "original_text",
    "page_text",
    "prompt",
    "query",
    "reason",
    "recipient_address",
    "recipient_email",
    "rationale",
    "replacement_text",
    "review_recommendation",
    "reviewer_id",
    "subject",
    "support_note",
    "text",
    "url",
}
SENSITIVE_HASH_SUFFIXES = (
    "_matched_text",
    "_original_text",
    "_query",
    "_reason",
    "_replacement_text",
    "_reviewer_id",
    "_text",
)
SENSITIVE_DROP_KEYS = {
    "api_key",
    "auth_header",
    "authorization",
    "ciphertext",
    "content",
    "cookie",
    "cookies",
    "document_base64",
    "mapping",
    "secret",
    "token",
}
SENSITIVE_DROP_SUFFIXES = ("_api_key", "_authorization", "_ciphertext", "_mapping", "_secret", "_token")
ADAPTER_TELEMETRY_ALLOWED_DETAIL_KEYS = {
    "adapter_version",
    "attachment_count",
    "auth_mode",
    "backend_status",
    "blocking_finding_count",
    "decision",
    "degraded_count",
    "degraded_modes",
    "document_hash",
    "document_id_hash",
    "elapsed_ms_bucket",
    "error_type",
    "failure_class",
    "failure_mode",
    "finding_count",
    "idempotency_key_hash",
    "matter_id_hash",
    "mode",
    "observed_user_action",
    "operation",
    "outcome",
    "policy_id",
    "policy_version",
    "recipient_count",
    "recipient_domain_count",
    "recommended_actions",
    "request_id",
    "required_actions",
    "retry_count",
    "review_id",
    "selector_kind",
    "send_allowed",
    "subject_hash",
    "tenant_hash",
    "timeout_ms",
}
ADAPTER_TELEMETRY_ALLOWED_OUTCOMES = {
    "blocked",
    "canceled",
    "denied",
    "failed",
    "held",
    "started",
    "succeeded",
    "warned",
}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256_text(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _truncate(value: str) -> str:
    if len(value) <= MAX_DETAIL_STRING_CHARS:
        return value
    return value[:MAX_DETAIL_STRING_CHARS] + "...[truncated]"


def _hash_field_name(key: str) -> str:
    return f"{key}_sha256"


def _is_sensitive_key_name(key: str) -> bool:
    normalized_key = key.lower()
    return (
        normalized_key in SENSITIVE_HASH_KEYS
        or normalized_key.endswith(SENSITIVE_HASH_SUFFIXES)
        or normalized_key in SENSITIVE_DROP_KEYS
        or normalized_key.endswith(SENSITIVE_DROP_SUFFIXES)
        or normalized_key in {"start_char", "end_char"}
    )


def _sanitize_value(key: str, value: Any) -> Any:
    normalized_key = key.lower()
    if normalized_key in SENSITIVE_DROP_KEYS or normalized_key.endswith(SENSITIVE_DROP_SUFFIXES):
        return "[redacted]"
    if normalized_key in SENSITIVE_HASH_KEYS or normalized_key.endswith(SENSITIVE_HASH_SUFFIXES):
        text = str(value or "")
        return {
            _hash_field_name(normalized_key): _sha256_text(text),
            "char_count": len(text),
            "present": bool(text),
        }
    if isinstance(value, Mapping):
        return sanitize_details(value)
    if isinstance(value, list):
        return [_sanitize_value(normalized_key, item) for item in value[:100]]
    if isinstance(value, tuple):
        return [_sanitize_value(normalized_key, item) for item in list(value)[:100]]
    if isinstance(value, str):
        return _truncate(value)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return _truncate(str(value))


def sanitize_details(details: Mapping[str, Any] | None) -> dict[str, Any]:
    if not details:
        return {}
    return {str(key): _sanitize_value(str(key), value) for key, value in details.items()}


def build_siem_event(
    *,
    event_type: str,
    category: str,
    action: str,
    outcome: str,
    request_id: str | None = None,
    review_id: str | None = None,
    details: Mapping[str, Any] | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ts": ts or _now_iso(),
        "event_type": event_type,
        "category": category,
        "action": action,
        "outcome": outcome,
        "request_id": request_id or "",
        "review_id": review_id or "",
        "details": sanitize_details(details),
    }


def build_privacy_ledger_siem_events(
    entries: list[Any],
    *,
    request_id: str | None,
    endpoint: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_entry in entries:
        entry = raw_entry.model_dump(mode="json") if hasattr(raw_entry, "model_dump") else dict(raw_entry)
        allowed = bool(entry.get("allowed", False))
        operation = str(entry.get("operation", "") or "privacy_operation")
        destination = str(entry.get("destination", "") or "")
        details = {
            "endpoint": endpoint,
            "operation": operation,
            "destination": destination,
            "allowed": allowed,
            "input_mode": str(entry.get("input_mode", "") or ""),
            "redactions": list(entry.get("redactions", []) or []),
            "reason": str(entry.get("reason", "") or ""),
            "content_sha256": str(entry.get("content_sha256", "") or ""),
            "content_type": str(entry.get("content_type", "") or ""),
        }
        query = str(entry.get("query", "") or "")
        if query:
            details["query"] = query
        events.append(
            build_siem_event(
                event_type="privacy_ledger",
                category="privacy",
                action=operation,
                outcome="allowed" if allowed else "blocked",
                request_id=request_id,
                details=details,
            )
        )
    return events


def build_journal_siem_event(entry: Any) -> dict[str, Any]:
    payload = dict(getattr(entry, "payload", {}) or {})
    details = {
        "journal_event_type": str(getattr(entry, "event_type", "") or ""),
        "seq": int(getattr(entry, "seq", 0) or 0),
        "key_version": str(getattr(entry, "key_version", "") or ""),
        "payload_keys": sorted(str(key) for key in payload if not _is_sensitive_key_name(str(key))),
        "payload_sha256": _sha256_text(json.dumps(payload, sort_keys=True, default=str)),
    }
    findings = payload.get("findings")
    if isinstance(findings, list):
        details["finding_count"] = len(findings)
        rule_ids = sorted(
            {
                _truncate(str(finding.get("rule_id") or finding.get("rule") or "").strip())
                for finding in findings
                if isinstance(finding, Mapping) and str(finding.get("rule_id") or finding.get("rule") or "").strip()
            }
        )
        if rule_ids:
            details["finding_rule_ids"] = rule_ids[:100]
    if str(getattr(entry, "event_type", "") or "") == "policy_decision_recorded":
        details.update(
            {
                "decision": str(payload.get("decision", "") or ""),
                "send_allowed": bool(payload.get("send_allowed", False)),
                "policy_id": str(payload.get("policy_id", "") or ""),
                "policy_version": str(payload.get("policy_version", "") or ""),
                "finding_count": int(payload.get("finding_count", 0) or 0),
                "blocking_finding_count": int(payload.get("blocking_finding_count", 0) or 0),
                "required_action_count": int(payload.get("required_action_count", 0) or 0),
                "recommended_action_count": int(payload.get("recommended_action_count", 0) or 0),
                "policy_reason_count": int(payload.get("policy_reason_count", 0) or 0),
                "degraded_mode_count": int(payload.get("degraded_mode_count", 0) or 0),
            }
        )
    return build_siem_event(
        event_type="journal_event",
        category="audit",
        action=str(getattr(entry, "event_type", "") or "journal_event"),
        outcome="sealed",
        review_id=str(getattr(entry, "review_id", "") or ""),
        details=details,
        ts=str(getattr(entry, "ts", "") or "") or None,
    )


def build_security_siem_event(
    *,
    action: str,
    outcome: str,
    request_id: str | None = None,
    review_id: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_siem_event(
        event_type="security_event",
        category="security",
        action=action,
        outcome=outcome,
        request_id=request_id,
        review_id=review_id,
        details=details,
    )


def _adapter_telemetry_category(event_name: str) -> str:
    lowered = event_name.lower()
    if "privacy" in lowered:
        return "privacy"
    if "auth" in lowered or "bypass" in lowered:
        return "security"
    return "audit"


def _adapter_telemetry_outcome(event_name: str, details: Mapping[str, Any]) -> str:
    supplied = str(details.get("outcome", "") or "").lower()
    if supplied in ADAPTER_TELEMETRY_ALLOWED_OUTCOMES:
        return supplied
    lowered = event_name.lower()
    if lowered.endswith("_review_started"):
        return "started"
    if lowered.endswith("_policy_decision_received"):
        return "succeeded"
    if lowered.endswith("_user_proceeded_after_warning"):
        return "warned"
    if lowered.endswith("_user_canceled"):
        return "canceled"
    if lowered.endswith("_user_rewrote"):
        return "succeeded"
    if lowered.endswith("_user_requested_approval") or lowered.endswith("_upload_held"):
        return "held"
    if lowered.endswith("_user_blocked") or lowered.endswith("_upload_blocked"):
        return "blocked"
    if lowered.endswith("_backend_failure") or lowered.endswith("_backend_timeout") or lowered.endswith(
        "_selector_failure"
    ):
        return "failed"
    decision = str(details.get("decision", "") or "").lower()
    if decision == "warn":
        return "warned"
    if decision in {"block", "rewrite_required"}:
        return "blocked"
    if decision == "approval_required":
        return "held"
    if decision == "allow":
        return "succeeded"
    return "succeeded"


def _adapter_telemetry_details(details: Mapping[str, Any]) -> dict[str, Any]:
    safe_details: dict[str, Any] = {}
    dropped_count = 0
    sanitized_prohibited_count = 0
    for raw_key, value in details.items():
        key = str(raw_key)
        normalized_key = key.lower()
        if normalized_key in ADAPTER_TELEMETRY_ALLOWED_DETAIL_KEYS:
            safe_details[normalized_key] = value
            continue
        if _is_sensitive_key_name(normalized_key):
            safe_details[normalized_key] = value
            sanitized_prohibited_count += 1
            continue
        dropped_count += 1
    if dropped_count:
        safe_details["dropped_detail_field_count"] = dropped_count
    if sanitized_prohibited_count:
        safe_details["sanitized_prohibited_field_count"] = sanitized_prohibited_count
    return safe_details


def build_adapter_telemetry_siem_event(event: Mapping[str, Any]) -> dict[str, Any]:
    details = event.get("details") if isinstance(event.get("details"), Mapping) else {}
    safe_details = _adapter_telemetry_details(details)
    schema_version = str(event.get("schema_version", "") or "")
    event_name = str(event.get("event_name", "") or "adapter_telemetry")
    surface = str(event.get("surface", "") or "")
    workflow = str(event.get("workflow", "") or "")
    adapter_version = str(event.get("adapter_version", "") or "")
    timestamp = str(event.get("timestamp", "") or "")
    if schema_version:
        safe_details["adapter_schema_version"] = schema_version
    if surface:
        safe_details["surface"] = surface
    if workflow:
        safe_details["workflow"] = workflow
    if adapter_version:
        safe_details["adapter_version"] = adapter_version
    if timestamp:
        safe_details["adapter_timestamp"] = timestamp
    request_id = str(event.get("request_id") or details.get("request_id") or "")
    review_id = str(event.get("review_id") or details.get("review_id") or "")
    return build_siem_event(
        event_type="adapter_telemetry",
        category=_adapter_telemetry_category(event_name),
        action=event_name,
        outcome=_adapter_telemetry_outcome(event_name, details),
        request_id=request_id,
        review_id=review_id,
        details=safe_details,
    )


def _syslog_address(raw_address: str) -> str | tuple[str, int]:
    if raw_address.startswith("udp://"):
        host_port = raw_address[len("udp://") :]
        host, _, raw_port = host_port.partition(":")
        return (host or "127.0.0.1", int(raw_port or "514"))
    return raw_address


def _emit_to_syslog(message: str, settings: Any) -> None:
    address = _syslog_address(str(getattr(settings, "syslog_address", "/var/run/syslog") or "/var/run/syslog"))
    facility = str(getattr(settings, "facility", "local4") or "local4")
    handler_kwargs: dict[str, Any] = {"address": address, "facility": facility}
    if isinstance(address, tuple):
        handler_kwargs["socktype"] = socket.SOCK_DGRAM
    handler = logging.handlers.SysLogHandler(**handler_kwargs)
    try:
        record = logging.LogRecord(
            name=str(getattr(settings, "app_name", "junas") or "junas"),
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        handler.emit(record)
    finally:
        handler.close()


def _load_siem_settings() -> Any | None:
    try:
        from junas.configs.runtime import get_runtime_settings

        return get_runtime_settings().siem
    except Exception:
        return None


def emit_siem_event(
    event: Mapping[str, Any],
    *,
    settings: Any | None = None,
    emit: Callable[[str], None] | None = None,
) -> bool:
    resolved_settings = settings if settings is not None else _load_siem_settings()
    if resolved_settings is None or not bool(getattr(resolved_settings, "enabled", False)):
        return False
    message = json.dumps(
        {
            "app": str(getattr(resolved_settings, "app_name", "junas") or "junas"),
            **dict(event),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    try:
        if emit is not None:
            emit(message)
        elif str(getattr(resolved_settings, "sink", "syslog") or "syslog") == "stdout":
            _logger.info(message)
        else:
            _emit_to_syslog(message, resolved_settings)
    except Exception:
        return False
    return True


def emit_privacy_ledger_events(
    entries: list[Any],
    *,
    request_id: str | None,
    endpoint: str,
    settings: Any | None = None,
    emit: Callable[[str], None] | None = None,
) -> int:
    count = 0
    for event in build_privacy_ledger_siem_events(entries, request_id=request_id, endpoint=endpoint):
        if emit_siem_event(event, settings=settings, emit=emit):
            count += 1
    return count


def emit_journal_event(
    entry: Any,
    *,
    settings: Any | None = None,
    emit: Callable[[str], None] | None = None,
) -> bool:
    return emit_siem_event(build_journal_siem_event(entry), settings=settings, emit=emit)


def emit_security_event(
    *,
    action: str,
    outcome: str,
    request_id: str | None = None,
    review_id: str | None = None,
    details: Mapping[str, Any] | None = None,
    settings: Any | None = None,
    emit: Callable[[str], None] | None = None,
) -> bool:
    return emit_siem_event(
        build_security_siem_event(
            action=action,
            outcome=outcome,
            request_id=request_id,
            review_id=review_id,
            details=details,
        ),
        settings=settings,
        emit=emit,
    )

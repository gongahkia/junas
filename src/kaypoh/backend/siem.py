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

SCHEMA_VERSION = "kaypoh.siem.v1"
MAX_DETAIL_STRING_CHARS = 256
_logger = logging.getLogger("kaypoh.siem")

SENSITIVE_HASH_KEYS = {
    "anonymized_text",
    "context_after",
    "context_before",
    "document_text",
    "matched_text",
    "original_text",
    "query",
    "reason",
    "rationale",
    "replacement_text",
    "review_recommendation",
    "reviewer_id",
    "text",
}
SENSITIVE_DROP_KEYS = {"api_key", "ciphertext", "content", "mapping", "secret"}


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


def _sanitize_value(key: str, value: Any) -> Any:
    normalized_key = key.lower()
    if normalized_key in SENSITIVE_DROP_KEYS:
        return "[redacted]"
    if normalized_key in SENSITIVE_HASH_KEYS:
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
        "payload_keys": sorted(str(key) for key in payload),
        "payload_sha256": _sha256_text(json.dumps(payload, sort_keys=True, default=str)),
    }
    findings = payload.get("findings")
    if isinstance(findings, list):
        details["finding_count"] = len(findings)
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
            name=str(getattr(settings, "app_name", "kaypoh") or "kaypoh"),
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
        from kaypoh.configs.runtime import get_runtime_settings

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
            "app": str(getattr(resolved_settings, "app_name", "kaypoh") or "kaypoh"),
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

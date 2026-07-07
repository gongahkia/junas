from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from junas.anonymize import DeterministicAnonymizer
from junas.review.engine import PreSendReviewEngine

PROTOCOL_VERSION = "2026-07-04"
STATE_STOPPED = "stopped"
STATE_RUNNING = "running"
STATE_PAUSED = "paused"
SUPPORTED_METHODS = (
    "initialize",
    "source.select",
    "transform.select",
    "output.select",
    "capture.start",
    "capture.pause",
    "capture.stop",
    "stats.snapshot",
    "shutdown",
)
CONTROL_METHODS = frozenset(SUPPORTED_METHODS)
SOURCE_KINDS = frozenset({"display", "window", "file", "clipboard"})
TRANSFORM_KINDS = frozenset({"review_only", "redaction_box", "anonymize"})
OUTPUT_KINDS = frozenset({"preview", "mp4", "obs", "none"})
ERROR_PARSE = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_STATE = -32000


class SidecarProtocolError(ValueError):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SidecarRequest:
    request_id: str | int | None
    method: str
    params: dict[str, Any]


@dataclass
class SidecarSession:
    state: str = STATE_STOPPED
    source: dict[str, Any] | None = None
    transform: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    frames_processed: int = 0
    files_processed: int = 0
    findings_count: int = 0
    runs_started: int = 0
    runs_succeeded: int = 0
    runs_failed: int = 0
    last_error: str = ""
    last_status: str = ""
    last_output: dict[str, Any] = field(default_factory=dict)
    should_exit: bool = False
    capabilities: tuple[str, ...] = field(default_factory=lambda: SUPPORTED_METHODS)
    review_engine_factory: Callable[[], Any] = PreSendReviewEngine
    anonymizer_factory: Callable[[], Any] = DeterministicAnonymizer

    def handle(self, raw: str) -> list[dict[str, Any]]:
        try:
            request = parse_request(raw)
            result = self._apply(request)
            messages = [success_response(request.request_id, result)]
            if request.method in {
                "source.select",
                "transform.select",
                "output.select",
                "capture.start",
                "capture.pause",
                "capture.stop",
            }:
                messages.append(stats_update(self.snapshot()))
            return messages
        except SidecarProtocolError as exc:
            request_id = _request_id_from_raw(raw)
            self.last_error = exc.message
            return [error_response(request_id, exc.code, exc.message)]

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "source": self.source or {},
            "transform": self.transform or {},
            "output": self.output or {},
            "frames_processed": self.frames_processed,
            "files_processed": self.files_processed,
            "findings_count": self.findings_count,
            "runs_started": self.runs_started,
            "runs_succeeded": self.runs_succeeded,
            "runs_failed": self.runs_failed,
            "last_status": self.last_status,
            "last_output": self.last_output,
            "last_error": self.last_error,
        }

    def _apply(self, request: SidecarRequest) -> dict[str, Any]:
        if request.method == "initialize":
            return {
                "protocol_version": PROTOCOL_VERSION,
                "capabilities": list(self.capabilities),
                "transport": "stdio-jsonrpc",
            }
        if request.method == "source.select":
            self._require_stopped_or_paused("source selection")
            self.source = _validated_selection(request.params, kind_key="kind", allowed=SOURCE_KINDS)
            return {"selected": self.source}
        if request.method == "transform.select":
            self._require_stopped_or_paused("transform selection")
            self.transform = _validated_selection(request.params, kind_key="kind", allowed=TRANSFORM_KINDS)
            return {"selected": self.transform}
        if request.method == "output.select":
            self._require_stopped_or_paused("output selection")
            self.output = _validated_selection(request.params, kind_key="kind", allowed=OUTPUT_KINDS)
            return {"selected": self.output}
        if request.method == "capture.start":
            if self.state == STATE_RUNNING:
                raise SidecarProtocolError(ERROR_STATE, "capture is already running")
            if not self.source:
                raise SidecarProtocolError(ERROR_STATE, "source must be selected before capture.start")
            if not self.transform:
                raise SidecarProtocolError(ERROR_STATE, "transform must be selected before capture.start")
            if not self.output:
                raise SidecarProtocolError(ERROR_STATE, "output must be selected before capture.start")
            self.state = STATE_RUNNING
            self.runs_started += 1
            if self.source.get("kind") in {"file", "clipboard"}:
                return self._run_one_shot()
            self.last_status = "running"
            return self.snapshot()
        if request.method == "capture.pause":
            if self.state != STATE_RUNNING:
                raise SidecarProtocolError(ERROR_STATE, "capture.pause requires running state")
            self.state = STATE_PAUSED
            return self.snapshot()
        if request.method == "capture.stop":
            self.state = STATE_STOPPED
            if self.last_status == "running":
                self.last_status = "stopped"
            return self.snapshot()
        if request.method == "stats.snapshot":
            return self.snapshot()
        if request.method == "shutdown":
            self.state = STATE_STOPPED
            if self.last_status == "running":
                self.last_status = "shutdown"
            self.should_exit = True
            return {"state": self.state, "should_exit": self.should_exit}
        raise SidecarProtocolError(ERROR_METHOD_NOT_FOUND, f"unsupported method: {request.method}")

    def _run_one_shot(self) -> dict[str, Any]:
        try:
            if self.source is None or self.transform is None or self.output is None:
                raise SidecarProtocolError(ERROR_STATE, "source, transform, and output are required")
            source_kind = str(self.source.get("kind") or "")
            if source_kind == "file":
                text = _read_file_source(self.source)
            elif source_kind == "clipboard":
                text = _clipboard_text_source(self.source)
            else:
                raise SidecarProtocolError(ERROR_INVALID_PARAMS, "one-shot execution requires file or clipboard source")
            output = _execute_text_transform(
                text,
                source=self.source,
                transform=self.transform,
                output=self.output,
                review_engine_factory=self.review_engine_factory,
                anonymizer_factory=self.anonymizer_factory,
            )
            self.frames_processed += 1
            if source_kind == "file":
                self.files_processed += 1
            self.findings_count += int(output.get("finding_count", 0) or 0)
            self.runs_succeeded += 1
            self.last_error = ""
            self.last_status = "completed"
            self.last_output = output
            self.state = STATE_STOPPED
            return self.snapshot()
        except SidecarProtocolError:
            self.runs_failed += 1
            self.last_status = "failed"
            self.state = STATE_STOPPED
            raise
        except Exception as exc:
            self.runs_failed += 1
            self.last_status = "failed"
            self.state = STATE_STOPPED
            raise SidecarProtocolError(ERROR_STATE, _safe_execution_error(exc)) from exc

    def _require_stopped_or_paused(self, action: str) -> None:
        if self.state == STATE_RUNNING:
            raise SidecarProtocolError(ERROR_STATE, f"{action} requires stopped or paused state")


def parse_request(raw: str) -> SidecarRequest:
    try:
        message = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SidecarProtocolError(ERROR_PARSE, "invalid JSON") from exc
    if not isinstance(message, dict):
        raise SidecarProtocolError(ERROR_INVALID_REQUEST, "request must be a JSON object")
    if message.get("jsonrpc") != "2.0":
        raise SidecarProtocolError(ERROR_INVALID_REQUEST, "jsonrpc must be 2.0")
    method = message.get("method")
    if not isinstance(method, str) or not method:
        raise SidecarProtocolError(ERROR_INVALID_REQUEST, "method must be a non-empty string")
    if method not in CONTROL_METHODS:
        raise SidecarProtocolError(ERROR_METHOD_NOT_FOUND, f"unsupported method: {method}")
    params = message.get("params", {})
    if not isinstance(params, dict):
        raise SidecarProtocolError(ERROR_INVALID_PARAMS, "params must be an object")
    request_id = message.get("id")
    if request_id is not None and not isinstance(request_id, str | int):
        raise SidecarProtocolError(ERROR_INVALID_REQUEST, "id must be a string, integer, or null")
    return SidecarRequest(request_id=request_id, method=method, params=params)


def success_response(request_id: str | int | None, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id: str | int | None, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def stats_update(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": "stats.update", "params": snapshot}


def encode_messages(messages: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(message, sort_keys=True) + "\n" for message in messages)


def _validated_selection(params: dict[str, Any], *, kind_key: str, allowed: frozenset[str]) -> dict[str, Any]:
    kind = params.get(kind_key)
    if not isinstance(kind, str) or kind not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise SidecarProtocolError(ERROR_INVALID_PARAMS, f"{kind_key} must be one of: {allowed_text}")
    selection = dict(params)
    if "id" in selection and not isinstance(selection["id"], str):
        raise SidecarProtocolError(ERROR_INVALID_PARAMS, "id must be a string when present")
    return selection


def _read_file_source(source: dict[str, Any]) -> str:
    raw_path = source.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SidecarProtocolError(ERROR_INVALID_PARAMS, "file source path is required")
    try:
        text = Path(raw_path).expanduser().read_text(encoding="utf-8")
    except OSError as exc:
        raise SidecarProtocolError(ERROR_STATE, "file source could not be read") from exc
    if not text.strip():
        raise SidecarProtocolError(ERROR_INVALID_PARAMS, "file source is empty")
    return text


def _clipboard_text_source(source: dict[str, Any]) -> str:
    text = source.get("text")
    if not isinstance(text, str) or not text.strip():
        raise SidecarProtocolError(ERROR_INVALID_PARAMS, "clipboard text is required")
    return text


def _execute_text_transform(
    text: str,
    *,
    source: dict[str, Any],
    transform: dict[str, Any],
    output: dict[str, Any],
    review_engine_factory: Callable[[], Any],
    anonymizer_factory: Callable[[], Any],
) -> dict[str, Any]:
    output_kind = str(output.get("kind") or "")
    if output_kind not in {"preview", "none"}:
        raise SidecarProtocolError(ERROR_INVALID_PARAMS, "one-shot execution supports preview or none output")
    transform_kind = str(transform.get("kind") or "")
    engine = review_engine_factory()
    review = engine.review(
        text=text,
        source_jurisdiction=str(transform.get("source_jurisdiction") or source.get("source_jurisdiction") or "SG"),
        destination_jurisdiction=str(
            transform.get("destination_jurisdiction") or source.get("destination_jurisdiction") or "SG"
        ),
        entity_id=None,
        include_suggestions=False,
        document_type=str(source.get("document_type") or "sidecar_text"),
        review_profile="strict",
    )
    finding_count = len(getattr(review, "findings", []) or [])
    result: dict[str, Any] = {
        "kind": output_kind,
        "source_kind": str(source.get("kind") or ""),
        "transform_kind": transform_kind,
        "status": "completed",
        "finding_count": finding_count,
        "degraded_count": len(getattr(review, "degraded_modes", []) or []),
        "overall_risk": str(getattr(getattr(review, "overall_risk", ""), "value", getattr(review, "overall_risk", ""))),
    }
    if transform_kind == "review_only":
        result["preview"] = {
            "finding_count": finding_count,
            "degraded_count": result["degraded_count"],
            "overall_risk": result["overall_risk"],
        }
        return result
    if transform_kind == "anonymize":
        anonymized = anonymizer_factory().anonymize(text=text, findings=list(getattr(review, "findings", []) or []))
        result["preview"] = {
            "text": anonymized.anonymized_text,
            "mapping_count": len(anonymized.mapping),
            "replacement_count": len(anonymized.replacements),
            "finding_count": finding_count,
        }
        return result
    raise SidecarProtocolError(ERROR_INVALID_PARAMS, "one-shot execution supports review_only or anonymize transform")


def _safe_execution_error(exc: Exception) -> str:
    if isinstance(exc, SidecarProtocolError):
        return exc.message
    return "execution failed"


def _request_id_from_raw(raw: str) -> str | int | None:
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(message, dict) and isinstance(message.get("id"), str | int):
        return message["id"]
    return None

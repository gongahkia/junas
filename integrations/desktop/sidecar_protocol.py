from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

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
    last_error: str = ""
    should_exit: bool = False
    capabilities: tuple[str, ...] = field(default_factory=lambda: SUPPORTED_METHODS)

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
            return self.snapshot()
        if request.method == "capture.pause":
            if self.state != STATE_RUNNING:
                raise SidecarProtocolError(ERROR_STATE, "capture.pause requires running state")
            self.state = STATE_PAUSED
            return self.snapshot()
        if request.method == "capture.stop":
            self.state = STATE_STOPPED
            return self.snapshot()
        if request.method == "stats.snapshot":
            return self.snapshot()
        if request.method == "shutdown":
            self.state = STATE_STOPPED
            self.should_exit = True
            return {"state": self.state, "should_exit": self.should_exit}
        raise SidecarProtocolError(ERROR_METHOD_NOT_FOUND, f"unsupported method: {request.method}")

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


def _request_id_from_raw(raw: str) -> str | int | None:
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(message, dict) and isinstance(message.get("id"), str | int):
        return message["id"]
    return None

#!/bin/bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./scripts/trace_policy_decision.sh --response-json <path> [--request-id <id>] [--siem-log <path>] [--tail-lines <n>]

Description:
  Print request id, policy id/version, decision, timings, and SIEM correlation status from a review response.
  The helper only emits bounded metadata. It does not print document text, findings, matched spans, or reasons.

Options:
  --response-json <path>  JSON response from /review, /safe-rewrite, /redact, /pseudonymize, or /anonymize (required)
  --request-id <id>       Override request id when the response was copied without request_id
  --siem-log <path>       Optional SIEM JSONL/stdout log to scan for a matching policy_decision_recorded event
  --tail-lines <n>        Number of SIEM log lines to scan from the end (default: 1000)
  --help                  Show this message

Examples:
  ./scripts/trace_policy_decision.sh --response-json reports/review.json
  ./scripts/trace_policy_decision.sh --response-json reports/review.json --siem-log reports/siem.jsonl
EOF
}

RESPONSE_JSON=""
REQUEST_ID=""
SIEM_LOG=""
TAIL_LINES="1000"

while [ $# -gt 0 ]; do
    case "$1" in
        --response-json)
            RESPONSE_JSON="${2:-}"
            shift 2
            ;;
        --request-id)
            REQUEST_ID="${2:-}"
            shift 2
            ;;
        --siem-log)
            SIEM_LOG="${2:-}"
            shift 2
            ;;
        --tail-lines)
            TAIL_LINES="${2:-}"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [ -z "${RESPONSE_JSON}" ]; then
    echo "--response-json is required" >&2
    usage >&2
    exit 1
fi

if [ ! -f "${RESPONSE_JSON}" ]; then
    echo "Response JSON not found: ${RESPONSE_JSON}" >&2
    exit 1
fi

if [ -n "${SIEM_LOG}" ] && [ ! -f "${SIEM_LOG}" ]; then
    echo "SIEM log not found: ${SIEM_LOG}" >&2
    exit 1
fi

if ! [[ "${TAIL_LINES}" =~ ^[0-9]+$ ]]; then
    echo "--tail-lines must be a non-negative integer" >&2
    exit 1
fi

python3 - "${RESPONSE_JSON}" "${REQUEST_ID}" "${SIEM_LOG}" "${TAIL_LINES}" <<'PY'
from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"cannot read response JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("response JSON root must be an object")
    return payload


def parse_event(line: str) -> dict[str, Any] | None:
    start = line.find("{")
    if start < 0:
        return None
    try:
        payload = json.loads(line[start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def iter_tail(path: str, max_lines: int):
    with Path(path).open("r", encoding="utf-8") as handle:
        yield from deque(handle, maxlen=max_lines)


def matching_policy_event(event: dict[str, Any], request_id: str, policy: dict[str, Any]) -> bool:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    if str(event.get("request_id") or "") not in {"", request_id}:
        return False
    if request_id not in {str(event.get("request_id") or ""), str(event.get("review_id") or "")}:
        return False
    if str(details.get("journal_event_type") or event.get("action") or "") != "policy_decision_recorded":
        return False
    if policy.get("policy_id") and str(details.get("policy_id") or "") != str(policy.get("policy_id")):
        return False
    if policy.get("policy_version") and str(details.get("policy_version") or "") != str(policy.get("policy_version")):
        return False
    return True


def compact_timings(value: Any) -> str:
    if not isinstance(value, dict):
        return "{}"
    timings = {
        str(key): value[key]
        for key in sorted(value)
        if isinstance(value[key], (int, float)) and not isinstance(value[key], bool)
    }
    return json.dumps(timings, sort_keys=True, separators=(",", ":"))


response_path, override_request_id, siem_log, raw_tail_lines = sys.argv[1:5]
tail_lines = int(raw_tail_lines)
response = load_json(response_path)
policy = response.get("policy_decision") if isinstance(response.get("policy_decision"), dict) else {}
request_id = (
    override_request_id
    or str(response.get("request_id") or "")
    or str(policy.get("review_id") or "")
)
if not request_id:
    raise SystemExit("request_id not found; pass --request-id")

print(f"request_id={request_id}")
print(f"policy_id={policy.get('policy_id') or ''}")
print(f"policy_version={policy.get('policy_version') or ''}")
print(f"decision={policy.get('decision') or ''}")
print(f"send_allowed={str(policy.get('send_allowed')).lower() if 'send_allowed' in policy else ''}")
print(f"timings_ms={compact_timings(response.get('timings_ms'))}")

if not siem_log:
    print("siem_event_status=not_checked")
    raise SystemExit(0)

matched: dict[str, Any] | None = None
for line in iter_tail(siem_log, tail_lines):
    event = parse_event(line)
    if event is not None and matching_policy_event(event, request_id, policy):
        matched = event

if matched is None:
    print("siem_event_status=missing")
else:
    print("siem_event_status=found")
    print(f"siem_schema_version={matched.get('schema_version') or ''}")
    print(f"siem_event_type={matched.get('event_type') or ''}")
    print(f"siem_action={matched.get('action') or ''}")
    print(f"siem_outcome={matched.get('outcome') or ''}")
PY

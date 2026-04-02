#!/bin/bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./scripts/trace_request_logs.sh --log-file <path> --request-id <uuid> [--tail-lines <n>] [--no-follow]

Description:
  Tail backend logs and filter by a single X-Request-ID so one request can be debugged end-to-end quickly.

Options:
  --log-file <path>     Log file to read (required)
  --request-id <id>     X-Request-ID value to filter for (required)
  --tail-lines <n>      Number of trailing lines to include before filtering (default: 300)
  --no-follow           Print current matching lines and exit (default is follow mode)
  --help                Show this message

Examples:
  ./scripts/trace_request_logs.sh --log-file reports/backend.log --request-id 8d35aafe-6f12-4fb6-8b66-7994028aaf13
  ./scripts/trace_request_logs.sh --log-file reports/backend.log --request-id 8d35aafe-6f12-4fb6-8b66-7994028aaf13 --no-follow
EOF
}

LOG_FILE=""
REQUEST_ID=""
TAIL_LINES="300"
FOLLOW="1"

while [ $# -gt 0 ]; do
    case "$1" in
        --log-file)
            LOG_FILE="${2:-}"
            shift 2
            ;;
        --request-id)
            REQUEST_ID="${2:-}"
            shift 2
            ;;
        --tail-lines)
            TAIL_LINES="${2:-}"
            shift 2
            ;;
        --no-follow)
            FOLLOW="0"
            shift
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

if [ -z "${LOG_FILE}" ]; then
    echo "--log-file is required" >&2
    usage >&2
    exit 1
fi

if [ -z "${REQUEST_ID}" ]; then
    echo "--request-id is required" >&2
    usage >&2
    exit 1
fi

if ! [[ "${TAIL_LINES}" =~ ^[0-9]+$ ]]; then
    echo "--tail-lines must be a non-negative integer" >&2
    exit 1
fi

if [ ! -f "${LOG_FILE}" ]; then
    echo "Log file not found: ${LOG_FILE}" >&2
    exit 1
fi

if command -v rg >/dev/null 2>&1; then
    if [ "${FOLLOW}" = "1" ]; then
        echo "Following ${LOG_FILE} for request_id=${REQUEST_ID} ..."
        tail -n "${TAIL_LINES}" -f "${LOG_FILE}" | rg --line-buffered --fixed-strings "${REQUEST_ID}"
    else
        if ! tail -n "${TAIL_LINES}" "${LOG_FILE}" | rg --fixed-strings "${REQUEST_ID}"; then
            echo "No matching lines found for request_id=${REQUEST_ID} in last ${TAIL_LINES} lines."
        fi
    fi
    exit 0
fi

if [ "${FOLLOW}" = "1" ]; then
    echo "Following ${LOG_FILE} for request_id=${REQUEST_ID} ..."
    tail -n "${TAIL_LINES}" -f "${LOG_FILE}" | grep --line-buffered -F "${REQUEST_ID}"
else
    if ! tail -n "${TAIL_LINES}" "${LOG_FILE}" | grep -F "${REQUEST_ID}"; then
        echo "No matching lines found for request_id=${REQUEST_ID} in last ${TAIL_LINES} lines."
    fi
fi

#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-${ROOT_DIR}/observability/alertmanager/alertmanager.env}"
OUTPUT_FILE="${2:-${ROOT_DIR}/observability/alertmanager/generated/alertmanager.production.yml}"
TEMPLATE_FILE="${ROOT_DIR}/observability/alertmanager/alertmanager.production.tmpl.yml"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

: "${ALERTMANAGER_SLACK_WEBHOOK_URL:?ALERTMANAGER_SLACK_WEBHOOK_URL must be set}"
: "${ALERTMANAGER_SLACK_CHANNEL:?ALERTMANAGER_SLACK_CHANNEL must be set}"
: "${ALERTMANAGER_PAGERDUTY_ROUTING_KEY:?ALERTMANAGER_PAGERDUTY_ROUTING_KEY must be set}"
: "${ALERTMANAGER_PRODUCT_WEBHOOK_URL:?ALERTMANAGER_PRODUCT_WEBHOOK_URL must be set}"

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\\/&]/\\&/g'
}

mkdir -p "$(dirname "${OUTPUT_FILE}")"

sed \
  -e "s/__SLACK_WEBHOOK_URL__/$(escape_sed_replacement "${ALERTMANAGER_SLACK_WEBHOOK_URL}")/g" \
  -e "s/__SLACK_CHANNEL__/$(escape_sed_replacement "${ALERTMANAGER_SLACK_CHANNEL}")/g" \
  -e "s/__PAGERDUTY_ROUTING_KEY__/$(escape_sed_replacement "${ALERTMANAGER_PAGERDUTY_ROUTING_KEY}")/g" \
  -e "s/__PRODUCT_WEBHOOK_URL__/$(escape_sed_replacement "${ALERTMANAGER_PRODUCT_WEBHOOK_URL}")/g" \
  "${TEMPLATE_FILE}" > "${OUTPUT_FILE}"

echo "Rendered ${OUTPUT_FILE}"

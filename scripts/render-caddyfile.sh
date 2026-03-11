#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-${ROOT_DIR}/compose.production.env}"
OUTPUT_FILE="${2:-${ROOT_DIR}/deploy/caddy/Caddyfile}"
TEMPLATE_FILE="${ROOT_DIR}/deploy/caddy/Caddyfile.template"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

: "${KILTER_TOGETHER_PUBLIC_HOST:?KILTER_TOGETHER_PUBLIC_HOST must be set}"
: "${KILTER_TOGETHER_ACME_EMAIL:?KILTER_TOGETHER_ACME_EMAIL must be set}"

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\\/&]/\\&/g'
}

PUBLIC_HOST_ESCAPED="$(escape_sed_replacement "${KILTER_TOGETHER_PUBLIC_HOST}")"
ACME_EMAIL_ESCAPED="$(escape_sed_replacement "${KILTER_TOGETHER_ACME_EMAIL}")"

mkdir -p "$(dirname "${OUTPUT_FILE}")"

sed \
  -e "s/__PUBLIC_HOST__/${PUBLIC_HOST_ESCAPED}/g" \
  -e "s/__ACME_EMAIL__/${ACME_EMAIL_ESCAPED}/g" \
  "${TEMPLATE_FILE}" > "${OUTPUT_FILE}"

echo "Rendered ${OUTPUT_FILE}"

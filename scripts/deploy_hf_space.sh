#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'usage: %s <hf-namespace/space-name>\n' "${0##*/}" >&2
  exit 64
fi

SPACE_ID="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPACE_SUBDOMAIN="${SPACE_ID/\//-}"
PUBLIC_DEMO_URL="${JUNAS_PUBLIC_DEMO_URL:-https://${SPACE_SUBDOMAIN}.hf.space}"

command -v hf >/dev/null

if [[ -z "${HF_TOKEN:-}" ]]; then
  WHOAMI="$(hf auth whoami 2>&1 || true)"
  if [[ "$WHOAMI" == *"Not logged in"* || -z "$WHOAMI" ]]; then
    printf 'hf auth required: run `hf auth login` or set HF_TOKEN\n' >&2
    exit 69
  fi
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/junas-hf-space.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

cp "$ROOT/deploy/huggingface-space/README.md" "$TMP/README.md"
cp "$ROOT/Dockerfile.public-demo" "$TMP/Dockerfile"
cp "$ROOT/pyproject.toml" "$ROOT/uv.lock" "$ROOT/config.toml" "$TMP/"
mkdir -p "$TMP/src"
cp -R "$ROOT/src/." "$TMP/src/"

if [[ -n "${HF_TOKEN:-}" ]]; then
  hf repo create "$SPACE_ID" --repo-type space --space-sdk docker --exist-ok --token "$HF_TOKEN"
  hf upload "$SPACE_ID" "$TMP" . --repo-type space --commit-message "Deploy Junas deterministic demo" --token "$HF_TOKEN"
else
  hf repo create "$SPACE_ID" --repo-type space --space-sdk docker --exist-ok
  hf upload "$SPACE_ID" "$TMP" . --repo-type space --commit-message "Deploy Junas deterministic demo"
fi

printf '%s\n' "$PUBLIC_DEMO_URL"

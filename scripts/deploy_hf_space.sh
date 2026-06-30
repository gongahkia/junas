#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'usage: %s <hf-namespace/space-name>\n' "${0##*/}" >&2
  exit 64
fi

SPACE_ID="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v hf >/dev/null

TOKEN_ARGS=()
if [[ -n "${HF_TOKEN:-}" ]]; then
  TOKEN_ARGS=(--token "$HF_TOKEN")
else
  hf auth whoami >/dev/null
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/junas-hf-space.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

cp "$ROOT/deploy/huggingface-space/README.md" "$TMP/README.md"
cp "$ROOT/Dockerfile.public-demo" "$TMP/Dockerfile"
cp "$ROOT/pyproject.toml" "$ROOT/uv.lock" "$ROOT/config.toml" "$TMP/"
mkdir -p "$TMP/src"
cp -R "$ROOT/src/." "$TMP/src/"

hf repo create "$SPACE_ID" --repo-type space --space-sdk docker --exist-ok "${TOKEN_ARGS[@]}"
hf upload "$SPACE_ID" "$TMP" . --repo-type space --commit-message "Deploy Junas deterministic demo" "${TOKEN_ARGS[@]}"

printf 'https://huggingface.co/spaces/%s\n' "$SPACE_ID"

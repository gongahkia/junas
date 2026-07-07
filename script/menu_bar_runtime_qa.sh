#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APP_BINARY="$ROOT_DIR/dist/JunasMenuBar.app/Contents/MacOS/JunasMenuBar"
TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/junas-menu-bar-runtime-qa.XXXXXX")
INVALID_SIDECAR="$TMP_DIR/invalid-sidecar"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

{
  printf '#!/bin/sh\n'
  printf "printf 'not-json\\\\n'\n"
  printf 'sleep 0.1\n'
} >"$INVALID_SIDECAR"
chmod +x "$INVALID_SIDECAR"

require_token() {
  token=$1
  file=$2
  if ! grep -Fq "$token" "$file"; then
    printf 'missing_token=%s file=%s\n' "$token" "$file" >&2
    exit 1
  fi
}

run_scenario() {
  scenario=$1
  shift
  output="$TMP_DIR/$scenario.out"
  if ! env JUNAS_MENU_BAR_RUNTIME_QA=1 JUNAS_MENU_BAR_QA_SCENARIO="$scenario" "$@" "$APP_BINARY" >"$output" 2>&1; then
    cat "$output"
    exit 1
  fi
  cat "$output"
}

printf 'menu_bar_runtime_qa_start date=2026-07-07\n'
"$ROOT_DIR/script/build_and_run.sh" --bundle-only >/dev/null

run_scenario normal JUNAS_SIDECAR_COMMAND="uv run junas sidecar stdio"
require_token "normal_launch=pass" "$TMP_DIR/normal.out"
require_token "sidecar_child_launch=pass" "$TMP_DIR/normal.out"
require_token "override_command=pass" "$TMP_DIR/normal.out"
require_token "app_shutdown=pass" "$TMP_DIR/normal.out"

run_scenario unavailable JUNAS_SIDECAR_COMMAND="/definitely/missing/junas-sidecar"
require_token "sidecar_unavailable=pass" "$TMP_DIR/unavailable.out"
require_token "override_unavailable_command=pass" "$TMP_DIR/unavailable.out"

run_scenario invalid_response JUNAS_SIDECAR_COMMAND="$INVALID_SIDECAR"
require_token "invalid_sidecar_response=pass" "$TMP_DIR/invalid_response.out"

run_scenario packaged_resource
require_token "packaged_resource_lookup=" "$TMP_DIR/packaged_resource.out"

printf 'menu_bar_runtime_qa=pass\n'

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASK_SOURCE="${1:-$ROOT/packaging/homebrew/Casks/aki.rb}"
TAP="junas/cask-verify"
TAP_DIR="$(brew --repository)/Library/Taps/junas/homebrew-cask-verify"

if [[ ! -f "$CASK_SOURCE" ]]; then
  printf 'cask source not found: %s\n' "$CASK_SOURCE" >&2
  exit 66
fi

cleanup() {
  brew untap "$TAP" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
brew tap-new --no-git "$TAP" >/dev/null
mkdir -p "$TAP_DIR/Casks"
cp "$CASK_SOURCE" "$TAP_DIR/Casks/aki.rb"
brew style "$TAP_DIR/Casks/aki.rb"
printf 'homebrew_cask_style_verified: true | tap: %s | cask: %s\n' "$TAP" "$CASK_SOURCE"

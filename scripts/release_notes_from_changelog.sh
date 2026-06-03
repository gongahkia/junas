#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/release_notes_from_changelog.sh --version VERSION --tag TAG

Prints GitHub Release notes from the matching CHANGELOG.md section.
EOF
}

VERSION=""
TAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      VERSION="$2"
      shift 2
      ;;
    --tag)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      TAG="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "$VERSION" ]] || { echo "--version is required" >&2; exit 2; }
[[ -n "$TAG" ]] || { echo "--tag is required" >&2; exit 2; }
[[ "$TAG" == "v$VERSION" ]] || {
  echo "release tag '$TAG' must be v$VERSION" >&2
  exit 1
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

section="$(
  awk -v tag="$TAG" '
    /^## / {
      if (found) {
        exit
      }
      if ($0 ~ "^## " tag "([[:space:]-]|$)") {
        found = 1
        next
      }
    }
    found {
      print
    }
  ' CHANGELOG.md
)"

if [[ -z "${section//[[:space:]]/}" ]]; then
  echo "CHANGELOG.md has no notes for $TAG" >&2
  exit 1
fi

cat <<EOF
# Aki ${VERSION}

${section}

## Install

\`\`\`console
\$ brew tap gongahkia/aki
\$ brew install --cask aki
\`\`\`

The cask installs the signed and notarized DMG attached to this release.
EOF

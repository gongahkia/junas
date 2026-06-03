#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/check_release_metadata.sh --version VERSION --tag TAG

Verifies release metadata that must agree before publishing a GitHub Release.
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

cargo_version="$(awk -F '"' '/^version =/ { print $2; exit }' Cargo.toml)"
cask_version="$(awk -F '"' '/^[[:space:]]*version / { print $2; exit }' Casks/aki.rb)"
readme_badge="[![Version $VERSION](https://img.shields.io/badge/version-$VERSION-blue)](./Cargo.toml)"

[[ "$cargo_version" == "$VERSION" ]] || {
  echo "Cargo.toml version '$cargo_version' does not match $VERSION" >&2
  exit 1
}

[[ "$cask_version" == "$VERSION" ]] || {
  echo "Casks/aki.rb version '$cask_version' does not match $VERSION" >&2
  exit 1
}

grep -Fq "$readme_badge" README.md || {
  echo "README.md version badge does not match $VERSION" >&2
  exit 1
}

grep -Eq "^## ${TAG}([[:space:]-]|$)" CHANGELOG.md || {
  echo "CHANGELOG.md is missing a release section for $TAG" >&2
  exit 1
}

grep -Fq "Aki-${VERSION}-macos.dmg" CHANGELOG.md || {
  echo "CHANGELOG.md release section must link the Aki-${VERSION}-macos.dmg artifact" >&2
  exit 1
}

grep -Fq "Aki-${VERSION}-macos.dmg.sha256" CHANGELOG.md || {
  echo "CHANGELOG.md release section must link the Aki-${VERSION}-macos.dmg.sha256 artifact" >&2
  exit 1
}

grep -Fq "releases/download/v#{version}/Aki-#{version}-macos.dmg" Casks/aki.rb || {
  echo "Casks/aki.rb must point at the versioned GitHub Release DMG" >&2
  exit 1
}

echo "release metadata ok: version=$VERSION tag=$TAG"

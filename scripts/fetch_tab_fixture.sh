#!/usr/bin/env bash
set -euo pipefail

repo_url="${TAB_REPO_URL:-https://github.com/NorskRegnesentral/text-anonymization-benchmark.git}"
dest="${1:-test/fixtures/external/text-anonymization-benchmark}"
branch="${TAB_BRANCH:-master}"

mkdir -p "$(dirname "$dest")"
if [[ -d "$dest/.git" ]]; then
  chmod -R u+w "$dest"
  git -C "$dest" fetch --depth 1 origin "$branch"
  git -C "$dest" checkout -f FETCH_HEAD
  git -C "$dest" clean -fdx
else
  git clone --depth 1 --branch "$branch" "$repo_url" "$dest"
fi
chmod -R a-w "$dest"
git -C "$dest" rev-parse HEAD

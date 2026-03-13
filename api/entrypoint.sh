#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
  set -- serve
fi

if [ "${1}" = "serve" ] && [ "${KILTER_TOGETHER_AUTO_BOOTSTRAP_IF_MISSING:-}" = "true" ]; then
  shift
  exec ./api serve --bootstrap-if-missing "$@"
fi

exec ./api "$@"

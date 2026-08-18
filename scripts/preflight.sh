#!/usr/bin/env bash

set -euo pipefail

failed=0
for dependency in python3 git curl tar; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    printf '[knowledge-addon][preflight] missing bootstrap dependency: %s\n' "$dependency" >&2
    failed=1
  fi
done

if ! python3 -m venv --help >/dev/null 2>&1 && ! python3 -m pip --version >/dev/null 2>&1; then
  printf '[knowledge-addon][preflight] Python needs either venv support or pip for the managed Qdrant runtime\n' >&2
  failed=1
fi

[[ "$failed" -eq 0 ]] || exit 2
printf '[knowledge-addon][preflight] local bootstrap prerequisites OK\n'

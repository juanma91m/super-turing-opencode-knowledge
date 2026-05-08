#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/knowledge_env.sh"

if [[ "$#" -eq 0 ]]; then
  printf 'Uso: knowledge_search.sh --query "texto" [filtros]\n' >&2
  exit 2
fi

args=("$@")
if [[ "$1" != --* ]]; then
  args=(--query "$*")
fi

python_bin="$(knowledge_require_python)"
script_py="$(knowledge_script_py)"
lock_file="$(knowledge_lock_file)"

mkdir -p "$(dirname "$lock_file")"

exec flock -s "$lock_file" "$python_bin" "$script_py" search "${args[@]}"

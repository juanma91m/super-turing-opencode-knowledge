#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/knowledge_env.sh"

if [[ "$#" -eq 0 ]]; then
  cat >&2 <<'EOF'
Uso:
  knowledge_store.sh store-path --path <archivo|directorio> [opciones]
  knowledge_store.sh store-text --title <titulo> --text <texto> [opciones]
EOF
  exit 2
fi

python_bin="$(knowledge_require_python)"
script_py="$(knowledge_script_py)"
lock_file="$(knowledge_lock_file)"

mkdir -p "$(dirname "$lock_file")"

exec flock -x "$lock_file" "$python_bin" "$script_py" "$@"

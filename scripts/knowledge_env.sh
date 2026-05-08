#!/usr/bin/env bash

set -euo pipefail

knowledge_home() {
  printf '%s\n' "${OPENCODE_KNOWLEDGE_HOME:-$HOME/.local/share/super-turing-opencode-knowledge}"
}

knowledge_qdrant_path() {
  printf '%s\n' "${QDRANT_LOCAL_PATH:-$(knowledge_home)/qdrant}"
}

knowledge_venv() {
  printf '%s\n' "${OPENCODE_KNOWLEDGE_VENV:-$(knowledge_home)/.venv}"
}

knowledge_lock_file() {
  printf '%s\n' "$(knowledge_home)/locks/qdrant.lock"
}

knowledge_python() {
  local venv_dir
  venv_dir="$(knowledge_venv)"
  if [[ -x "$venv_dir/bin/python" ]]; then
    printf '%s\n' "$venv_dir/bin/python"
    return 0
  fi
  return 1
}

knowledge_script_py() {
  local script_dir
  script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  printf '%s\n' "$script_dir/knowledge_store.py"
}

knowledge_require_python() {
  local python_bin
  if python_bin="$(knowledge_python)"; then
    printf '%s\n' "$python_bin"
    return 0
  fi

  printf 'Knowledge Qdrant no instalado. Corré: bash ~/.config/opencode/scripts/install-knowledge-qdrant.sh (o install-knowledge.sh)\n' >&2
  return 1
}

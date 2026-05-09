#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_ENV_FILE="$SCRIPT_DIR/knowledge_env.local.sh"

if [[ -f "$LOCAL_ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$LOCAL_ENV_FILE"
fi

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
  printf '%s\n' "$SCRIPT_DIR/knowledge_store.py"
}

knowledge_embedding_backend() {
  printf '%s\n' "${OPENCODE_KNOWLEDGE_EMBEDDING_BACKEND:-fastembed}"
}

knowledge_embedding_model() {
  printf '%s\n' "${OPENCODE_KNOWLEDGE_EMBEDDING_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"
}

knowledge_ollama_base_url() {
  printf '%s\n' "${OPENCODE_KNOWLEDGE_OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
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

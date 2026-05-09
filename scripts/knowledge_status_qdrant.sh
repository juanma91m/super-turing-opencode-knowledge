#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/knowledge_env.sh"

python_bin="$(knowledge_require_python)"
script_py="$(knowledge_script_py)"
lock_file="$(knowledge_lock_file)"

export OPENCODE_KNOWLEDGE_EMBEDDING_BACKEND="${OPENCODE_KNOWLEDGE_EMBEDDING_BACKEND:-$(knowledge_embedding_backend)}"
export OPENCODE_KNOWLEDGE_EMBEDDING_MODEL="${OPENCODE_KNOWLEDGE_EMBEDDING_MODEL:-$(knowledge_embedding_model)}"
export OPENCODE_KNOWLEDGE_OLLAMA_BASE_URL="${OPENCODE_KNOWLEDGE_OLLAMA_BASE_URL:-$(knowledge_ollama_base_url)}"

mkdir -p "$(dirname "$lock_file")"

exec flock -s "$lock_file" "$python_bin" "$script_py" status "$@"

#!/usr/bin/env bash

set -euo pipefail

KNOWLEDGE_HOME_DEFAULT="${HOME}/.local/share/super-turing-opencode-knowledge"
KNOWLEDGE_HOME="${OPENCODE_KNOWLEDGE_HOME:-$KNOWLEDGE_HOME_DEFAULT}"
QDRANT_LOCAL_PATH="${QDRANT_LOCAL_PATH:-$KNOWLEDGE_HOME/qdrant}"
VENV_DIR="${OPENCODE_KNOWLEDGE_VENV:-$KNOWLEDGE_HOME/.venv}"
EMBEDDING_MODEL="${OPENCODE_KNOWLEDGE_EMBEDDING_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"
RECREATE=0

usage() {
  cat <<'EOF'
Usage: install-knowledge-qdrant.sh [options]

Options:
  --home <path>          Base directory for the knowledge layer state
  --qdrant-path <path>   Local file-based Qdrant path
  --venv <path>          Virtualenv path for Python dependencies
  --model <name>         Embedding model name (default: sentence-transformers/all-MiniLM-L6-v2)
  --recreate             Recreate the virtualenv from scratch
  -h, --help             Show this help
EOF
}

log() {
  printf '[knowledge-qdrant-install] %s\n' "$*"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --home)
      KNOWLEDGE_HOME="$2"
      shift 2
      ;;
    --qdrant-path)
      QDRANT_LOCAL_PATH="$2"
      shift 2
      ;;
    --venv)
      VENV_DIR="$2"
      shift 2
      ;;
    --model)
      EMBEDDING_MODEL="$2"
      shift 2
      ;;
    --recreate)
      RECREATE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  printf 'python3 es requerido para instalar el componente Qdrant del knowledge layer\n' >&2
  exit 1
fi

create_virtualenv() {
  local target_dir="$1"

  if python3 -m venv "$target_dir" >/dev/null 2>&1; then
    return 0
  fi

  if ! python3 -m pip --version >/dev/null 2>&1; then
    printf 'No se pudo crear el virtualenv con python3 -m venv y python3 -m pip tampoco está disponible\n' >&2
    return 1
  fi

  log "Fallback: instalando virtualenv en user-space"
  python3 -m pip install --user --break-system-packages virtualenv >/dev/null
  python3 -m virtualenv "$target_dir" >/dev/null
}

if [[ "$RECREATE" -eq 1 ]] && [[ -d "$VENV_DIR" ]]; then
  log "Recreando virtualenv en $VENV_DIR"
  rm -rf "$VENV_DIR"
fi

mkdir -p "$KNOWLEDGE_HOME" "$QDRANT_LOCAL_PATH" "$KNOWLEDGE_HOME/locks"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  log "Creando virtualenv en $VENV_DIR"
  create_virtualenv "$VENV_DIR"
fi

if ! "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
  log "El virtualenv existente no tiene pip usable; recreando $VENV_DIR"
  rm -rf "$VENV_DIR"
  create_virtualenv "$VENV_DIR"
fi

log "Actualizando pip/setuptools/wheel"
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel >/dev/null

log "Instalando dependencias de Qdrant local + embeddings"
"$VENV_DIR/bin/python" -m pip install "qdrant-client[fastembed]>=1.10,<2" >/dev/null

log "Validando import y paths"
QDRANT_LOCAL_PATH="$QDRANT_LOCAL_PATH" \
OPENCODE_KNOWLEDGE_EMBEDDING_MODEL="$EMBEDDING_MODEL" \
"$VENV_DIR/bin/python" - <<'PY'
import os
from pathlib import Path

from qdrant_client import QdrantClient

db_path = Path(os.environ["QDRANT_LOCAL_PATH"]).expanduser()
client = QdrantClient(path=str(db_path))
client.get_collections()
print("Knowledge Qdrant listo en", db_path)
PY

log "Listo. Home: $KNOWLEDGE_HOME"
log "Qdrant local path: $QDRANT_LOCAL_PATH"
log "Venv: $VENV_DIR"
log "Modelo por defecto: $EMBEDDING_MODEL"

#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/knowledge_env.sh"

OUTPUT=""
COMPONENTS="all"
ENGRAM_DB="${HOME}/.engram/engram.db"
ENGRAM_BIN="${HOME}/.opencode/bin/engram"
QDRANT_PATH="$(knowledge_qdrant_path)"
ADDON_MANIFEST="$REPO_DIR/KNOWLEDGE-MANIFEST.json"
if [[ ! -f "$ADDON_MANIFEST" && -f "$REPO_DIR/.opencode-knowledge-addon.json" ]]; then
  ADDON_MANIFEST="$REPO_DIR/.opencode-knowledge-addon.json"
fi

usage() {
  cat <<'EOF'
Usage: knowledge_backup.sh [options]

Options:
  --output <archive>       Output .tar.gz path (default: ./opencode-knowledge-backup-<timestamp>.tar.gz)
  --components <value>     all | engram | qdrant (default: all)
  --engram-db <path>       Engram SQLite path
  --engram-bin <path>      Engram binary path
  --qdrant-path <path>     Qdrant local storage path
  -h, --help               Show this help
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT="$2"; shift 2 ;;
    --components) COMPONENTS="$2"; shift 2 ;;
    --engram-db) ENGRAM_DB="$2"; shift 2 ;;
    --engram-bin) ENGRAM_BIN="$2"; shift 2 ;;
    --qdrant-path) QDRANT_PATH="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n\n' "$1" >&2; usage >&2; exit 1 ;;
  esac
done

case "$COMPONENTS" in all|engram|qdrant) ;; *) printf 'Invalid components: %s\n' "$COMPONENTS" >&2; exit 1 ;; esac

if [[ -z "$OUTPUT" ]]; then
  OUTPUT="$PWD/opencode-knowledge-backup-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
fi

qdrant_version=""
if python_bin="$(knowledge_python 2>/dev/null)"; then
  qdrant_version="$("$python_bin" -c 'import importlib.metadata; print(importlib.metadata.version("qdrant-client"))')"
fi
if [[ "$COMPONENTS" == "all" || "$COMPONENTS" == "qdrant" ]] && [[ -z "$qdrant_version" ]]; then
  printf 'Qdrant runtime not available; install it before creating a Qdrant backup.\n' >&2
  exit 1
fi

lock_file="$(knowledge_lock_file)"
mkdir -p "$(dirname "$lock_file")"
exec 9>"$lock_file"
flock -x 9

python3 "$SCRIPT_DIR/knowledge_backup.py" create \
  --output "$OUTPUT" \
  --components "$COMPONENTS" \
  --engram-db "$ENGRAM_DB" \
  --engram-bin "$ENGRAM_BIN" \
  --qdrant-path "$QDRANT_PATH" \
  --qdrant-client-version "$qdrant_version" \
  --embedding-backend "$(knowledge_embedding_backend)" \
  --embedding-model "$(knowledge_embedding_model)" \
  --addon-manifest "$ADDON_MANIFEST"

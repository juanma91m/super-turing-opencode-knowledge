#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE="all"
ARGS=()

usage() {
  cat <<'EOF'
Usage: knowledge_status.sh [options]

Modes:
  --engram-only      Show only Engram component status
  --qdrant-only      Show only Qdrant component status
  --all              Show both components (default)

Advanced Qdrant status flags should be passed directly to knowledge_status_qdrant.sh.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --engram-only)
      MODE="engram"
      shift
      ;;
    --qdrant-only)
      MODE="qdrant"
      shift
      ;;
    --all)
      MODE="all"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

case "$MODE" in
  engram)
    exec bash "$SCRIPT_DIR/knowledge_status_engram.sh" "${ARGS[@]}"
    ;;
  qdrant)
    exec bash "$SCRIPT_DIR/knowledge_status_qdrant.sh" "${ARGS[@]}"
    ;;
  all)
    if [[ "${#ARGS[@]}" -gt 0 ]]; then
      printf 'knowledge_status.sh en modo agregado no acepta flags avanzados; usá --engram-only o --qdrant-only para status por componente.\n' >&2
      exit 2
    fi
    printf '## Engram\n'
    bash "$SCRIPT_DIR/knowledge_status_engram.sh"
    printf '\n## Qdrant\n'
    exec bash "$SCRIPT_DIR/knowledge_status_qdrant.sh"
    ;;
esac

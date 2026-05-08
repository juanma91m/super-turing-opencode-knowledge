#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE="qdrant"
FORWARD_ARGS=()

usage() {
  cat <<'EOF'
Usage: install-knowledge.sh [options]

Modes:
  --qdrant-only      Install only the Qdrant component (default; backward-compatible)
  --engram-only      Install only the Engram component
  --all              Install both components

Advanced per-component options should be passed directly to:
  - install-knowledge-engram.sh
  - install-knowledge-qdrant.sh

This wrapper keeps the old default behavior for compatibility: running it without mode flags installs only the Qdrant component.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --qdrant-only)
      MODE="qdrant"
      shift
      ;;
    --engram-only)
      MODE="engram"
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
      FORWARD_ARGS+=("$1")
      shift
      ;;
  esac
done

case "$MODE" in
  qdrant)
    exec bash "$SCRIPT_DIR/install-knowledge-qdrant.sh" "${FORWARD_ARGS[@]}"
    ;;
  engram)
    exec bash "$SCRIPT_DIR/install-knowledge-engram.sh" "${FORWARD_ARGS[@]}"
    ;;
  all)
    if [[ "${#FORWARD_ARGS[@]}" -gt 0 ]]; then
      printf 'install-knowledge.sh --all no reenvía argumentos avanzados. Usá los scripts por componente si necesitás opciones específicas.\n' >&2
      exit 2
    fi
    bash "$SCRIPT_DIR/install-knowledge-engram.sh"
    exec bash "$SCRIPT_DIR/install-knowledge-qdrant.sh"
    ;;
esac

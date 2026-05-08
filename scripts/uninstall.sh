#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="${HOME}/.config/opencode"
DRY_RUN=0
MANAGED_FILES=()

usage() {
  cat <<'EOF'
Usage: uninstall.sh [options]

Options:
  --target-dir <path>   Target OpenCode config dir (default: ~/.config/opencode)
  --dry-run             Show actions without writing files
  -h, --help            Show this help
EOF
}

load_managed_files() {
  mapfile -t MANAGED_FILES < <(
    python3 - "$REPO_DIR/KNOWLEDGE-MANIFEST.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text())
for item in data.get("managedFiles", []):
    print(item)
PY
  )
}

log() {
  printf '[knowledge-addon-uninstall] %s\n' "$*"
}

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] %s\n' "$*"
    return 0
  fi
  "$@"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --target-dir)
      TARGET_DIR="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
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
  printf 'python3 is required to read KNOWLEDGE-MANIFEST.json\n' >&2
  exit 1
fi

load_managed_files
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$TARGET_DIR/.knowledge-addon-backups/uninstall-$TIMESTAMP"

for rel_path in "${MANAGED_FILES[@]}"; do
  src="$TARGET_DIR/$rel_path"
  if [[ ! -e "$src" ]]; then
    continue
  fi
  run mkdir -p "$(dirname "$BACKUP_DIR/$rel_path")"
  run cp -R "$src" "$BACKUP_DIR/$rel_path"
  run rm -f "$src"
done

log "Assets del addon removidos de $TARGET_DIR"
log "Estado runtime/local de Engram y Qdrant no se borra automáticamente en esta fase"

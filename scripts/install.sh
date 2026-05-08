#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="${HOME}/.config/opencode"
DRY_RUN=0
VALIDATE=1
ASSETS_ONLY=0
MODE="all"
MANAGED_FILES=()

usage() {
  cat <<'EOF'
Usage: install.sh [options]

Options:
  --target-dir <path>   Target OpenCode config dir (default: ~/.config/opencode)
  --engram-only         Bootstrap only the Engram runtime after copying assets
  --qdrant-only         Bootstrap only the Qdrant runtime after copying assets
  --all                 Bootstrap both runtimes after copying assets (default)
  --assets-only         Copy assets only; do not run runtime installers
  --dry-run             Show actions without writing files
  --no-validate         Do not run opencode debug config after install
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
  printf '[knowledge-addon] %s\n' "$*"
}

warn() {
  printf '[knowledge-addon][warn] %s\n' "$*" >&2
}

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] %s\n' "$*"
    return 0
  fi
  "$@"
}

backup_path() {
  local rel_path="$1"
  local src="$TARGET_DIR/$rel_path"
  local backup_dir="$2"

  if [[ ! -e "$src" ]]; then
    return 0
  fi

  run mkdir -p "$(dirname "$backup_dir/$rel_path")"
  run cp -R "$src" "$backup_dir/$rel_path"
}

copy_file() {
  local rel_path="$1"
  local src="$REPO_DIR/$rel_path"
  local dst="$TARGET_DIR/$rel_path"

  if [[ ! -e "$src" ]]; then
    warn "Managed file missing in source: $rel_path"
    return 0
  fi

  run mkdir -p "$(dirname "$dst")"
  run cp "$src" "$dst"
}

run_runtime_installers() {
  if [[ "$ASSETS_ONLY" -eq 1 ]]; then
    log "Assets copiados; se omite bootstrap runtime por --assets-only"
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "Dry-run: se omite bootstrap runtime"
    return 0
  fi

  case "$MODE" in
    engram)
      log "Bootstrappeando componente Engram"
      bash "$TARGET_DIR/scripts/install-knowledge-engram.sh"
      ;;
    qdrant)
      log "Bootstrappeando componente Qdrant"
      bash "$TARGET_DIR/scripts/install-knowledge-qdrant.sh"
      ;;
    all)
      log "Bootstrappeando componente Engram"
      bash "$TARGET_DIR/scripts/install-knowledge-engram.sh"
      log "Bootstrappeando componente Qdrant"
      bash "$TARGET_DIR/scripts/install-knowledge-qdrant.sh"
      ;;
  esac
}

validate_config() {
  if [[ "$VALIDATE" -ne 1 ]]; then
    return 0
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "Dry-run: se omite opencode debug config"
    return 0
  fi
  if [[ "$TARGET_DIR" != "$HOME/.config/opencode" ]]; then
    warn "El target no es ~/.config/opencode; se omite opencode debug config automático"
    return 0
  fi
  if ! command -v opencode >/dev/null 2>&1; then
    warn "opencode no está disponible; se omite validación"
    return 0
  fi

  log "Validando configuración efectiva"
  opencode debug config >/dev/null
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --target-dir)
      TARGET_DIR="$2"
      shift 2
      ;;
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
    --assets-only)
      ASSETS_ONLY=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-validate)
      VALIDATE=0
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
BACKUP_DIR="$TARGET_DIR/.knowledge-addon-backups/$TIMESTAMP"

log "Repo dir: $REPO_DIR"
log "Target dir: $TARGET_DIR"

run mkdir -p "$TARGET_DIR"

for rel_path in "${MANAGED_FILES[@]}"; do
  backup_path "$rel_path" "$BACKUP_DIR"
done

for rel_path in "${MANAGED_FILES[@]}"; do
  copy_file "$rel_path"
done

run_runtime_installers
validate_config

log "Instalación del addon knowledge finalizada"

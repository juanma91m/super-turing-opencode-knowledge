#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="${HOME}/.config/opencode"
MANAGED_FILES=()

usage() {
  cat <<'EOF'
Usage: status.sh [options]

Options:
  --target-dir <path>   Target OpenCode config dir (default: ~/.config/opencode)
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

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --target-dir)
      TARGET_DIR="$2"
      shift 2
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

missing=0
mismatched=0

for rel_path in "${MANAGED_FILES[@]}"; do
  src="$REPO_DIR/$rel_path"
  dst="$TARGET_DIR/$rel_path"
  if [[ ! -e "$dst" ]]; then
    missing=$((missing + 1))
    continue
  fi
  if ! cmp -s "$src" "$dst"; then
    mismatched=$((mismatched + 1))
  fi
done

printf 'target_dir=%s\n' "$TARGET_DIR"
printf 'managed_files_total=%s\n' "${#MANAGED_FILES[@]}"
printf 'managed_files_missing=%s\n' "$missing"
printf 'managed_files_mismatched=%s\n' "$mismatched"
printf 'engram_assets_present=%s\n' "$([[ -f "$TARGET_DIR/scripts/install-knowledge-engram.sh" ]] && printf yes || printf no)"
printf 'qdrant_assets_present=%s\n' "$([[ -f "$TARGET_DIR/scripts/install-knowledge-qdrant.sh" ]] && printf yes || printf no)"

printf '\n## Engram runtime\n'
if [[ -f "$TARGET_DIR/scripts/knowledge_status_engram.sh" ]]; then
  bash "$TARGET_DIR/scripts/knowledge_status_engram.sh"
else
  printf 'engram_status_script_present=no\n'
fi

printf '\n## Qdrant runtime\n'
if [[ -f "$TARGET_DIR/scripts/knowledge_status_qdrant.sh" ]]; then
  bash "$TARGET_DIR/scripts/knowledge_status_qdrant.sh"
else
  printf 'qdrant_status_script_present=no\n'
fi

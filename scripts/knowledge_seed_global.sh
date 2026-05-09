#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
MANIFEST_PATH="$CONFIG_ROOT/knowledge/global_seed_paths.txt"
COLLECTION="global-opencode-knowledge"
PROJECT="opencode-stack"
SCOPE="global"
SOURCE_TYPE="stack-doc"

usage() {
  cat <<'EOF'
Usage: knowledge_seed_global.sh [options]

Options:
  --manifest <path>      Manifest file with one relative path per line
  --collection <name>    Target Qdrant collection (default: global-opencode-knowledge)
  --project <name>       Project tag stored in payload (default: opencode-stack)
  --scope <name>         Scope tag stored in payload (default: global)
  --source-type <type>   Source type metadata (default: stack-doc)
  -h, --help             Show this help
EOF
}

log() {
  printf '[knowledge-seed-global] %s\n' "$*"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --manifest)
      MANIFEST_PATH="$2"
      shift 2
      ;;
    --collection)
      COLLECTION="$2"
      shift 2
      ;;
    --project)
      PROJECT="$2"
      shift 2
      ;;
    --scope)
      SCOPE="$2"
      shift 2
      ;;
    --source-type)
      SOURCE_TYPE="$2"
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

if [[ ! -f "$MANIFEST_PATH" ]]; then
  printf 'Manifest not found: %s\n' "$MANIFEST_PATH" >&2
  exit 1
fi

store_script="$SCRIPT_DIR/knowledge_store.sh"
if [[ ! -f "$store_script" ]]; then
  printf 'Knowledge wrapper not found: %s\n' "$store_script" >&2
  exit 1
fi

indexed=0
skipped=0

while IFS= read -r rel_path || [[ -n "$rel_path" ]]; do
  [[ -z "$rel_path" ]] && continue
  [[ "$rel_path" =~ ^# ]] && continue

  abs_path="$CONFIG_ROOT/$rel_path"
  if [[ ! -e "$abs_path" ]]; then
    log "Skipping missing path: $rel_path"
    skipped=$((skipped + 1))
    continue
  fi

  log "Indexing: $rel_path"
  bash "$store_script" store-path \
    --source-root "$CONFIG_ROOT" \
    --scope "$SCOPE" \
    --project "$PROJECT" \
    --collection "$COLLECTION" \
    --source-type "$SOURCE_TYPE" \
    --path "$abs_path" >/dev/null
  indexed=$((indexed + 1))
done < "$MANIFEST_PATH"

log "Done. indexed=$indexed skipped=$skipped collection=$COLLECTION"

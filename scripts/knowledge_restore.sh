#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/knowledge_env.sh"

ARCHIVE=""
COMPONENTS="all"
ENGRAM_DB="${HOME}/.engram/engram.db"
ENGRAM_BIN="${HOME}/.opencode/bin/engram"
QDRANT_PATH="$(knowledge_qdrant_path)"
CONFIRMED=0
VERIFY_ONLY=0
ALLOW_ENGRAM_VERSION_MISMATCH=0
ALLOW_QDRANT_VERSION_MISMATCH=0
ALLOW_EMBEDDING_MISMATCH=0

usage() {
  cat <<'EOF'
Usage: knowledge_restore.sh --archive <path> [options]

Options:
  --archive <path>         Backup archive to verify or restore
  --components <value>     all | engram | qdrant (default: all)
  --engram-db <path>       Destination Engram SQLite path
  --engram-bin <path>      Engram binary used only for active-process detection
  --qdrant-path <path>     Destination Qdrant local storage path
  --verify-only            Validate manifest, checksums and SQLite without restoring
  --confirm-restore        Required for any restore
  --allow-engram-version-mismatch   Explicitly accept a different Engram runtime
  --allow-qdrant-version-mismatch   Explicitly accept a different qdrant-client version
  --allow-embedding-mismatch        Explicitly accept different embedding settings
  -h, --help               Show this help

Close OpenCode and every Engram process before restoring Engram.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --archive) ARCHIVE="$2"; shift 2 ;;
    --components) COMPONENTS="$2"; shift 2 ;;
    --engram-db) ENGRAM_DB="$2"; shift 2 ;;
    --engram-bin) ENGRAM_BIN="$2"; shift 2 ;;
    --qdrant-path) QDRANT_PATH="$2"; shift 2 ;;
    --verify-only) VERIFY_ONLY=1; shift ;;
    --confirm-restore) CONFIRMED=1; shift ;;
    --allow-engram-version-mismatch) ALLOW_ENGRAM_VERSION_MISMATCH=1; shift ;;
    --allow-qdrant-version-mismatch) ALLOW_QDRANT_VERSION_MISMATCH=1; shift ;;
    --allow-embedding-mismatch) ALLOW_EMBEDDING_MISMATCH=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n\n' "$1" >&2; usage >&2; exit 1 ;;
  esac
done

[[ -n "$ARCHIVE" ]] || { printf 'Missing required --archive\n' >&2; exit 1; }
case "$COMPONENTS" in all|engram|qdrant) ;; *) printf 'Invalid components: %s\n' "$COMPONENTS" >&2; exit 1 ;; esac

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  exec python3 "$SCRIPT_DIR/knowledge_backup.py" verify --archive "$ARCHIVE"
fi
if [[ "$CONFIRMED" -ne 1 ]]; then
  printf 'Refusing restore without --confirm-restore. Use --verify-only first.\n' >&2
  exit 1
fi

if [[ "$COMPONENTS" == "all" || "$COMPONENTS" == "engram" ]]; then
  if [[ ! -x "$ENGRAM_BIN" ]]; then
    printf 'Engram runtime not available: %s\n' "$ENGRAM_BIN" >&2
    exit 1
  fi
  if command -v pgrep >/dev/null 2>&1 && pgrep -f "${ENGRAM_BIN} (mcp|serve|tui)" >/dev/null 2>&1; then
    printf 'Active Engram process detected. Close OpenCode/Engram before restoring.\n' >&2
    exit 1
  fi
fi

lock_file="$(knowledge_lock_file)"
mkdir -p "$(dirname "$lock_file")"
exec 9>"$lock_file"
flock -x 9

rollback_dir="$(knowledge_home)/restore-backups/$(date -u +%Y%m%dT%H%M%SZ)"
engram_version=""
if [[ -x "$ENGRAM_BIN" ]]; then
  engram_version="$("$ENGRAM_BIN" version)"
fi
qdrant_version=""
if python_bin="$(knowledge_python 2>/dev/null)"; then
  qdrant_version="$("$python_bin" -c 'import importlib.metadata; print(importlib.metadata.version("qdrant-client"))')"
fi
if [[ "$COMPONENTS" == "all" || "$COMPONENTS" == "qdrant" ]] && [[ -z "$qdrant_version" ]]; then
  printf 'Qdrant runtime not available; install it before restoring Qdrant.\n' >&2
  exit 1
fi

extra_args=()
[[ "$ALLOW_ENGRAM_VERSION_MISMATCH" -eq 1 ]] && extra_args+=(--allow-engram-version-mismatch)
[[ "$ALLOW_QDRANT_VERSION_MISMATCH" -eq 1 ]] && extra_args+=(--allow-qdrant-version-mismatch)
[[ "$ALLOW_EMBEDDING_MISMATCH" -eq 1 ]] && extra_args+=(--allow-embedding-mismatch)

exec python3 "$SCRIPT_DIR/knowledge_backup.py" restore \
  --archive "$ARCHIVE" \
  --components "$COMPONENTS" \
  --engram-db "$ENGRAM_DB" \
  --qdrant-path "$QDRANT_PATH" \
  --rollback-dir "$rollback_dir" \
  --engram-version "$engram_version" \
  --qdrant-client-version "$qdrant_version" \
  --embedding-backend "$(knowledge_embedding_backend)" \
  --embedding-model "$(knowledge_embedding_model)" \
  "${extra_args[@]}" \
  --confirm-restore

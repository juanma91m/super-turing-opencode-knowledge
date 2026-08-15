#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
KNOWLEDGE_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
ENGRAM_EXPECTED_REF="1dafc0f63051b2214100f7bd801357e4aab61c26"
ENGRAM_BIN="${HOME}/.opencode/bin/engram"
ENGRAM_DB="${HOME}/.engram/engram.db"
ENGRAM_SRC_DIR="${HOME}/.local/src/engram-opencode-stack"
CONFIG_DIR="${HOME}/.config/opencode"
PATCH_FILE="$KNOWLEDGE_DIR/patches/engram-source-agent.patch"

usage() {
  cat <<'EOF'
Usage: knowledge_status_engram.sh [options]

Options:
  --bin <path>         Engram binary path (default: ~/.opencode/bin/engram)
  --db <path>          Engram DB path (default: ~/.engram/engram.db)
  --src-dir <path>     Engram source checkout path (default: ~/.local/src/engram-opencode-stack)
  --config-dir <path>  OpenCode config dir to inspect MCP config (default: ~/.config/opencode)
  -h, --help           Show this help
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --bin)
      ENGRAM_BIN="$2"
      shift 2
      ;;
    --db)
      ENGRAM_DB="$2"
      shift 2
      ;;
    --src-dir)
      ENGRAM_SRC_DIR="$2"
      shift 2
      ;;
    --config-dir)
      CONFIG_DIR="$2"
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

mcp_enabled="unknown"
if [[ -f "$CONFIG_DIR/opencode.json" ]] && command -v python3 >/dev/null 2>&1; then
  mcp_enabled="$(python3 - "$CONFIG_DIR/opencode.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text())
    enabled = data.get("mcp", {}).get("engram", {}).get("enabled")
    if enabled is True:
        print("yes")
    elif enabled is False:
        print("no")
    else:
        print("unknown")
except Exception:
    print("unknown")
PY
)"
fi

printf 'engram_bin=%s\n' "$ENGRAM_BIN"
printf 'engram_bin_present=%s\n' "$([[ -x "$ENGRAM_BIN" ]] && printf yes || printf no)"
printf 'engram_db=%s\n' "$ENGRAM_DB"
printf 'engram_db_present=%s\n' "$([[ -f "$ENGRAM_DB" ]] && printf yes || printf no)"
printf 'engram_src_dir=%s\n' "$ENGRAM_SRC_DIR"
printf 'engram_src_dir_present=%s\n' "$([[ -d "$ENGRAM_SRC_DIR/.git" ]] && printf yes || printf no)"
printf 'engram_expected_ref=%s\n' "$ENGRAM_EXPECTED_REF"
if [[ -d "$ENGRAM_SRC_DIR/.git" ]]; then
  actual_ref="$(git -C "$ENGRAM_SRC_DIR" rev-parse HEAD 2>/dev/null || true)"
  printf 'engram_actual_ref=%s\n' "${actual_ref:-unknown}"
  printf 'engram_ref_matches=%s\n' "$([[ "$actual_ref" == "$ENGRAM_EXPECTED_REF" ]] && printf yes || printf no)"
  if [[ -f "$PATCH_FILE" ]] && git -C "$ENGRAM_SRC_DIR" apply --reverse --check "$PATCH_FILE" >/dev/null 2>&1; then
    printf 'engram_patch_applied=yes\n'
  elif [[ -f "$PATCH_FILE" ]]; then
    printf 'engram_patch_applied=no\n'
  else
    printf 'engram_patch_applied=unknown\n'
  fi
else
  printf 'engram_actual_ref=unknown\n'
  printf 'engram_ref_matches=unknown\n'
  printf 'engram_patch_applied=unknown\n'
fi
if [[ -x "$ENGRAM_BIN" ]]; then
  version_output="$("$ENGRAM_BIN" --version 2>/dev/null || true)"
  version_output="${version_output##*$'\n'}"
  printf 'engram_version=%s\n' "${version_output:-unknown}"
else
  printf 'engram_version=unknown\n'
fi
printf 'engram_mcp_enabled=%s\n' "$mcp_enabled"

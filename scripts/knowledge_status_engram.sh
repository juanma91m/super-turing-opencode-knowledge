#!/usr/bin/env bash

set -euo pipefail

ENGRAM_BIN="${HOME}/.opencode/bin/engram"
ENGRAM_DB="${HOME}/.engram/engram.db"
ENGRAM_SRC_DIR="${HOME}/.local/src/engram-opencode-stack"
CONFIG_DIR="${HOME}/.config/opencode"

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
printf 'engram_mcp_enabled=%s\n' "$mcp_enabled"

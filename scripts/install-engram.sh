#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

printf '[install-engram][deprecated] Usá install-knowledge-engram.sh; este wrapper legacy sigue funcionando por compatibilidad.\n' >&2
exec bash "$SCRIPT_DIR/install-knowledge-engram.sh" "$@"

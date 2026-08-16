#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
PROJECTS=""
BIND_ADDRESS="127.0.0.1"
PORT="18080"
CLIENT_CONFIG=""
CLIENT_SERVER_URL=""

usage() {
  cat <<'EOF'
Usage: init-env.sh --projects <comma-separated-existing-projects> [options]

Options:
  --projects <list>       Explicit Engram project allowlist (required; no wildcard)
  --bind-address <ip>     Published host address (default: 127.0.0.1)
  --port <port>           Published host port (default: 18080)
  --client-config <path>  Also write a mode-0600 client config with the sync token
  --client-server <url>   URL stored in --client-config (required with that option)
  --force                 Replace an existing .env
  -h, --help              Show this help
EOF
}

FORCE=0
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --projects) PROJECTS="${2:-}"; shift 2 ;;
    --bind-address) BIND_ADDRESS="${2:-}"; shift 2 ;;
    --port) PORT="${2:-}"; shift 2 ;;
    --client-config) CLIENT_CONFIG="${2:-}"; shift 2 ;;
    --client-server) CLIENT_SERVER_URL="${2:-}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

PROJECTS="${PROJECTS//[[:space:]]/}"
if [[ -z "$PROJECTS" || "$PROJECTS" == *"*"* || "$PROJECTS" == ,* || "$PROJECTS" == *, || "$PROJECTS" == *",,"* ]]; then
  printf 'An explicit non-wildcard project allowlist is required\n' >&2
  exit 2
fi
if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  printf 'Invalid port: %s\n' "$PORT" >&2
  exit 2
fi
if [[ -n "$CLIENT_CONFIG" && ! "$CLIENT_SERVER_URL" =~ ^https?://[^[:space:]]+$ ]]; then
  printf 'A valid http(s) --client-server URL is required with --client-config\n' >&2
  exit 2
fi
if [[ -z "$CLIENT_CONFIG" && -n "$CLIENT_SERVER_URL" ]]; then
  printf -- '--client-server requires --client-config\n' >&2
  exit 2
fi
if [[ -e "$ENV_FILE" && "$FORCE" -ne 1 ]]; then
  printf '%s already exists; use --force only after preserving its secrets\n' "$ENV_FILE" >&2
  exit 1
fi
if [[ -n "$CLIENT_CONFIG" && -e "$CLIENT_CONFIG" && "$FORCE" -ne 1 ]]; then
  printf '%s already exists; use --force only after preserving it\n' "$CLIENT_CONFIG" >&2
  exit 1
fi

umask 077
postgres_password="$(openssl rand -hex 32)"
sync_token="$(openssl rand -hex 32)"
admin_token="$(openssl rand -hex 32)"
jwt_secret="$(openssl rand -hex 32)"

cat >"$ENV_FILE" <<EOF
ENGRAM_REF=1dafc0f63051b2214100f7bd801357e4aab61c26
ENGRAM_VERSION=1.20.1-0.20260814074340-1dafc0f63051+addon
POSTGRES_USER=engram
POSTGRES_PASSWORD=$postgres_password
POSTGRES_DB=engram_cloud
ENGRAM_CLOUD_TOKEN=$sync_token
ENGRAM_CLOUD_ADMIN=$admin_token
ENGRAM_JWT_SECRET=$jwt_secret
ENGRAM_CLOUD_ALLOWED_PROJECTS=$PROJECTS
ENGRAM_CLOUD_BIND_ADDRESS=$BIND_ADDRESS
ENGRAM_CLOUD_PORT=$PORT
EOF
chmod 600 "$ENV_FILE"

if [[ -n "$CLIENT_CONFIG" ]]; then
  mkdir -p "$(dirname "$CLIENT_CONFIG")"
  cat >"$CLIENT_CONFIG" <<EOF
OPENCODE_KNOWLEDGE_CLOUD_SERVER=$CLIENT_SERVER_URL
OPENCODE_KNOWLEDGE_CLOUD_TOKEN=$sync_token
OPENCODE_KNOWLEDGE_CLOUD_PROJECTS=$PROJECTS
OPENCODE_KNOWLEDGE_CLOUD_TIMEOUT_SECONDS=30
EOF
  chmod 600 "$CLIENT_CONFIG"
fi

printf 'Created %s with mode 0600\n' "$ENV_FILE"
printf 'Projects: %s\n' "$PROJECTS"
if [[ -n "$CLIENT_CONFIG" ]]; then
  printf 'Created client config %s with mode 0600; the token was not printed.\n' "$CLIENT_CONFIG"
else
  printf 'Copy ENGRAM_CLOUD_TOKEN into each client config; do not copy the admin/JWT/Postgres secrets.\n'
fi

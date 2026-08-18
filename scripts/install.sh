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
CLOUD_MODE="local-only"
CLOUD_SERVER_INPUT=""
CLOUD_TOKEN=""
CLOUD_PROJECTS=""
CLOUD_SERVER_URL=""
CLOUD_SERVER_HOST=""
CLOUD_SERVER_PORT=""
CLIENT_CONFIG="$TARGET_DIR/knowledge-sync.conf"
SERVER_ENV_FILE="$REPO_DIR/server/.env"

usage() {
  cat <<'EOF'
Usage: install.sh [options]

Options:
  --target-dir <path>   Target OpenCode config dir (default: ~/.config/opencode)
  --server-and-client   Install Engram Cloud Docker server and configure this PC as client
  --client-only         Configure this PC against an existing Engram Cloud server
  --local-only          Keep knowledge local; no Cloud server/client config (default)
  --cloud-server <host:port|url>
                        Server endpoint; prompted when omitted
  --cloud-token <token> Sync token for a fresh client-only config; prefer the secure prompt
  --cloud-projects <list>
                        Explicit comma-separated existing project allowlist
  --engram-only         Bootstrap only the Engram runtime after copying assets
  --qdrant-only         Bootstrap only the Qdrant runtime after copying assets
  --all                 Bootstrap both runtimes after copying assets (default)
  --assets-only         Copy assets only; do not run runtime installers
  --dry-run             Show actions without writing files
  --no-validate         Do not run opencode debug config after install
  -h, --help            Show this help
EOF
}

read_config_value() {
  local path="$1" key="$2"
  python3 - "$path" "$key" <<'PY'
import pathlib
import sys

path, key = pathlib.Path(sys.argv[1]), sys.argv[2]
if not path.is_file():
    raise SystemExit(0)
for raw in path.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    current, value = line.split("=", 1)
    if current.strip() == key:
        print(value.strip(), end="")
        break
PY
}

normalize_cloud_server() {
  local raw="$1" normalized
  normalized="$(python3 - "$raw" <<'PY'
import re
import sys
from urllib.parse import urlsplit

raw = sys.argv[1].strip().rstrip("/")
if not raw:
    raise SystemExit("Cloud server endpoint is required")
candidate = raw if "://" in raw else f"http://{raw}"
parsed = urlsplit(candidate)
if parsed.scheme not in {"http", "https"} or not parsed.hostname:
    raise SystemExit("Cloud server must be IP:PORT or an http(s) URL")
try:
    port = parsed.port
except ValueError as exc:
    raise SystemExit(str(exc))
if port is None or not 1 <= port <= 65535:
    raise SystemExit("Cloud server requires a valid explicit port")
if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
    raise SystemExit("Cloud server URL must not include credentials, path, query or fragment")
host = parsed.hostname
if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
    raise SystemExit("Only IPv4 addresses or DNS hostnames are supported")
print(f"{parsed.scheme}://{host}:{port}\t{host}\t{port}")
PY
  )" || exit 2
  IFS=$'\t' read -r CLOUD_SERVER_URL CLOUD_SERVER_HOST CLOUD_SERVER_PORT <<< "$normalized"
}

normalize_projects() {
  CLOUD_PROJECTS="${CLOUD_PROJECTS//[[:space:]]/}"
  if [[ -z "$CLOUD_PROJECTS" || "$CLOUD_PROJECTS" == *"*"* || "$CLOUD_PROJECTS" == ,* || "$CLOUD_PROJECTS" == *, || "$CLOUD_PROJECTS" == *",,"* ]]; then
    printf 'An explicit comma-separated non-wildcard project allowlist is required\n' >&2
    exit 2
  fi
}

resolve_cloud_mode() {
  CLIENT_CONFIG="$TARGET_DIR/knowledge-sync.conf"
}

prompt_cloud_server() {
  local default_value="${1:-}" prompt_value
  if [[ -n "$CLOUD_SERVER_INPUT" ]]; then
    normalize_cloud_server "$CLOUD_SERVER_INPUT"
    return 0
  fi
  if [[ ! -t 0 ]]; then
    printf '%s requires --cloud-server in non-interactive mode\n' "$CLOUD_MODE" >&2
    exit 2
  fi
  if [[ -n "$default_value" ]]; then
    read -r -p "IP:PUERTO o URL del servidor [$default_value]: " prompt_value
    CLOUD_SERVER_INPUT="${prompt_value:-$default_value}"
  else
    read -r -p 'IP:PUERTO o URL del servidor: ' CLOUD_SERVER_INPUT
  fi
  normalize_cloud_server "$CLOUD_SERVER_INPUT"
}

write_client_config() {
  local existing_server="" existing_token="" existing_projects=""
  if [[ -f "$CLIENT_CONFIG" ]]; then
    existing_server="$(read_config_value "$CLIENT_CONFIG" OPENCODE_KNOWLEDGE_CLOUD_SERVER)"
    existing_token="$(read_config_value "$CLIENT_CONFIG" OPENCODE_KNOWLEDGE_CLOUD_TOKEN)"
    existing_projects="$(read_config_value "$CLIENT_CONFIG" OPENCODE_KNOWLEDGE_CLOUD_PROJECTS)"
  fi
  prompt_cloud_server "$existing_server"
  [[ -n "$CLOUD_TOKEN" ]] || CLOUD_TOKEN="$existing_token"
  [[ -n "$CLOUD_PROJECTS" ]] || CLOUD_PROJECTS="$existing_projects"
  if [[ -z "$CLOUD_TOKEN" ]]; then
    if [[ ! -t 0 ]]; then
      printf 'A fresh client-only install requires --cloud-token\n' >&2
      exit 2
    fi
    read -rs -p 'Token de sincronización del servidor: ' CLOUD_TOKEN
    printf '\n' >&2
  fi
  if [[ -z "$CLOUD_PROJECTS" ]]; then
    if [[ ! -t 0 ]]; then
      printf 'A fresh client-only install requires --cloud-projects\n' >&2
      exit 2
    fi
    read -r -p 'Proyectos Engram existentes (separados por coma): ' CLOUD_PROJECTS
  fi
  [[ -n "$CLOUD_TOKEN" && "$CLOUD_TOKEN" != *[[:space:]]* ]] || {
    printf 'Cloud sync token must be non-empty and contain no whitespace\n' >&2
    exit 2
  }
  normalize_projects

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "Dry-run: se escribiría config cliente 0600 en $CLIENT_CONFIG para $CLOUD_SERVER_URL; el token no se muestra"
    return 0
  fi
  if [[ -f "$CLIENT_CONFIG" ]]; then
    mkdir -p "$BACKUP_DIR"
    cp "$CLIENT_CONFIG" "$BACKUP_DIR/knowledge-sync.conf"
    chmod 600 "$BACKUP_DIR/knowledge-sync.conf"
  fi
  umask 077
  mkdir -p "$(dirname "$CLIENT_CONFIG")"
  {
    printf 'OPENCODE_KNOWLEDGE_CLOUD_SERVER=%s\n' "$CLOUD_SERVER_URL"
    printf 'OPENCODE_KNOWLEDGE_CLOUD_TOKEN=%s\n' "$CLOUD_TOKEN"
    printf 'OPENCODE_KNOWLEDGE_CLOUD_PROJECTS=%s\n' "$CLOUD_PROJECTS"
    printf 'OPENCODE_KNOWLEDGE_CLOUD_TIMEOUT_SECONDS=30\n'
  } >"$CLIENT_CONFIG"
  chmod 600 "$CLIENT_CONFIG"
  log "Cliente Cloud configurado en $CLIENT_CONFIG; el token no se mostró"
}

prepare_sync_timer() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log 'Dry-run: se instalarían las unidades systemd user sin habilitar el timer'
    return 0
  fi
  if [[ "$TARGET_DIR" != "$HOME/.config/opencode" ]]; then
    warn "Target no activo; se omite instalación del timer systemd user"
    return 0
  fi
  if ! "$TARGET_DIR/scripts/knowledge-sync-timer" install; then
    warn "No se pudo instalar el timer systemd user; el sync manual sigue disponible"
  fi
  log 'El timer queda deshabilitado hasta completar enroll/doctor/bootstrap y un sync manual exitoso'
}

install_server_and_client() {
  local compose=(docker compose --env-file "$SERVER_ENV_FILE" -f "$REPO_DIR/server/compose.yaml")
  for dependency in docker openssl curl; do
    command -v "$dependency" >/dev/null 2>&1 || { printf '%s is required for server-and-client mode\n' "$dependency" >&2; exit 1; }
  done
  docker compose version >/dev/null

  if [[ -f "$SERVER_ENV_FILE" ]]; then
    [[ -f "$CLIENT_CONFIG" ]] || {
      printf '%s exists but %s does not; preserve secrets and repair the client config manually before retrying\n' "$SERVER_ENV_FILE" "$CLIENT_CONFIG" >&2
      exit 1
    }
    CLOUD_SERVER_URL="$(read_config_value "$CLIENT_CONFIG" OPENCODE_KNOWLEDGE_CLOUD_SERVER)"
    normalize_cloud_server "$CLOUD_SERVER_URL"
    log 'Se preservan server/.env y knowledge-sync.conf existentes; no se rotan secretos'
  else
    [[ ! -e "$CLIENT_CONFIG" ]] || {
      printf '%s already exists while server/.env is missing; refusing to replace its client secrets\n' "$CLIENT_CONFIG" >&2
      exit 1
    }
    prompt_cloud_server '127.0.0.1:18080'
    if [[ -z "$CLOUD_PROJECTS" ]]; then
      if [[ ! -t 0 ]]; then
        printf 'server-and-client requires --cloud-projects in non-interactive mode\n' >&2
        exit 2
      fi
      read -r -p 'Proyectos Engram existentes permitidos (separados por coma): ' CLOUD_PROJECTS
    fi
    normalize_projects
    python3 - "$CLOUD_SERVER_HOST" <<'PY'
import ipaddress
import sys

try:
    address = ipaddress.ip_address(sys.argv[1])
except ValueError:
    raise SystemExit("server-and-client requires an IP address, not a DNS hostname")
if address.version != 4:
    raise SystemExit("server-and-client currently supports IPv4 bind addresses")
PY
    if [[ "$DRY_RUN" -eq 1 ]]; then
      log "Dry-run: server/init-env.sh generaría secretos 0600, bind $CLOUD_SERVER_HOST:$CLOUD_SERVER_PORT y config cliente; ningún secreto se muestra"
    else
      "$REPO_DIR/server/init-env.sh" \
        --projects "$CLOUD_PROJECTS" \
        --bind-address "$CLOUD_SERVER_HOST" \
        --port "$CLOUD_SERVER_PORT" \
        --client-config "$CLIENT_CONFIG" \
        --client-server "$CLOUD_SERVER_URL"
    fi
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log 'Dry-run: se validaría Docker Compose y se levantarían PostgreSQL + Engram Cloud'
  else
    "${compose[@]}" config --quiet
    "${compose[@]}" up -d --build
    curl -fsS "$CLOUD_SERVER_URL/health" >/dev/null
    log "Engram Cloud saludable en $CLOUD_SERVER_URL"
  fi
  prepare_sync_timer
}

install_client_only() {
  write_client_config
  prepare_sync_timer
  if [[ "$DRY_RUN" -eq 0 ]] && ! command -v curl >/dev/null 2>&1; then
    warn 'curl no está disponible; se omite health check del servidor'
  elif [[ "$DRY_RUN" -eq 0 ]] && ! curl -fsS --max-time 5 "$CLOUD_SERVER_URL/health" >/dev/null; then
    warn "El servidor $CLOUD_SERVER_URL no respondió; el cliente local sigue instalado y puede sincronizar cuando vuelva a estar disponible"
  fi
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

ensure_primary_agent_templates() {
  local rel_path src dst
  for rel_path in agents/plan.md agents/build.md; do
    src="$REPO_DIR/$rel_path"
    dst="$TARGET_DIR/$rel_path"
    if [[ -e "$dst" ]]; then
      continue
    fi
    run mkdir -p "$(dirname "$dst")"
    run cp "$src" "$dst"
  done
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

list_augmented_agents() {
  local result=()
  local candidate
  for candidate in planner master-dev agent-design; do
    if [[ -f "$TARGET_DIR/agents/$candidate.md" ]] && grep -q 'KNOWLEDGE_AUTONOMY_START' "$TARGET_DIR/agents/$candidate.md" 2>/dev/null; then
      result+=("$candidate")
    fi
  done
  local IFS=,
  printf '%s' "${result[*]}"
}

apply_agent_autonomy() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "Dry-run: se omite parcheo de autonomía de agentes"
    return 0
  fi
  python3 "$REPO_DIR/scripts/manage_agent_autonomy.py" apply --target-dir "$TARGET_DIR"
}

configure_engram_mcp() {
  local config_path="$TARGET_DIR/opencode.json"
  local engram_bin="${HOME}/.opencode/bin/engram"
  local enabled="false"

  if [[ ! -f "$config_path" ]]; then
    warn "No existe $config_path; se omite wiring MCP de Engram"
    return 0
  fi

  if [[ "$ASSETS_ONLY" -eq 1 || "$MODE" == "qdrant" ]]; then
    log "Se preserva el wiring MCP de Engram actual"
    return 0
  fi

  if [[ -x "$engram_bin" ]]; then
    enabled="true"
  else
    warn "No se encontró Engram en $engram_bin; el bloque MCP de Engram se dejará deshabilitado"
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "Dry-run: se omite merge de MCP Engram en $config_path"
    return 0
  fi

  python3 "$REPO_DIR/scripts/manage_opencode_config.py" apply-engram --config "$config_path" --engram-bin "$engram_bin" --enabled "$enabled"
}

write_install_marker() {
  local augmented_agents
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "Dry-run: se omite escritura de marker del addon"
    return 0
  fi
  augmented_agents="$(list_augmented_agents)"
  python3 "$REPO_DIR/scripts/manage_install_marker.py" write \
    --target-dir "$TARGET_DIR" \
    --repo-dir "$REPO_DIR" \
    --mode "$MODE" \
    --assets-only "$([[ "$ASSETS_ONLY" -eq 1 ]] && printf true || printf false)" \
    --engram-mcp-managed "$([[ "$ASSETS_ONLY" -eq 1 || "$MODE" == "qdrant" ]] && printf false || printf true)" \
    --augmented-agents "$augmented_agents"
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
    --server-and-client)
      [[ "$CLOUD_MODE" == "local-only" ]] || { printf 'Choose only one cloud install mode\n' >&2; exit 2; }
      CLOUD_MODE="server-and-client"
      shift
      ;;
    --client-only)
      [[ "$CLOUD_MODE" == "local-only" ]] || { printf 'Choose only one cloud install mode\n' >&2; exit 2; }
      CLOUD_MODE="client-only"
      shift
      ;;
    --local-only)
      CLOUD_MODE="local-only"
      shift
      ;;
    --cloud-server)
      CLOUD_SERVER_INPUT="${2:-}"
      shift 2
      ;;
    --cloud-token)
      CLOUD_TOKEN="${2:-}"
      shift 2
      ;;
    --cloud-projects)
      CLOUD_PROJECTS="${2:-}"
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
resolve_cloud_mode
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

ensure_primary_agent_templates
run_runtime_installers
configure_engram_mcp
apply_agent_autonomy
write_install_marker
case "$CLOUD_MODE" in
  server-and-client) install_server_and_client ;;
  client-only) install_client_only ;;
  local-only) log 'Knowledge Cloud no configurado; estado local preservado' ;;
esac
validate_config

log "Instalación del addon knowledge finalizada"

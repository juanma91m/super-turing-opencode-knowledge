#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
KNOWLEDGE_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
ENGRAM_REPO_URL="https://github.com/Gentleman-Programming/engram.git"
ENGRAM_REF="64bf163d0b9b8533c4b5c9a2566db8464f75eac3"
ENGRAM_SRC_DIR="${HOME}/.local/src/engram-opencode-stack"
ENGRAM_BIN="${HOME}/.opencode/bin/engram"
GO_INSTALL_ROOT="${HOME}/.local/opt/go"
GO_VERSION="1.26.2"
DRY_RUN=0
SKIP_GO_INSTALL=0

usage() {
  cat <<'EOF'
Usage: install-knowledge-engram.sh [options]

Options:
  --src-dir <path>          Managed Engram source checkout (default: ~/.local/src/engram-opencode-stack)
  --bin <path>              Output binary path (default: ~/.opencode/bin/engram)
  --dry-run                 Show actions without writing files
  --skip-go-install         Do not auto-install Go if it is missing
  -h, --help                Show this help
EOF
}

log() {
  printf '[knowledge-engram-install] %s\n' "$*" >&2
}

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] %s\n' "$*"
    return 0
  fi
  "$@"
}

detect_go_bin() {
  if command -v go >/dev/null 2>&1; then
    command -v go
    return 0
  fi
  if [[ -x "$GO_INSTALL_ROOT/bin/go" ]]; then
    printf '%s\n' "$GO_INSTALL_ROOT/bin/go"
    return 0
  fi
  return 1
}

install_go_local() {
  local os arch url tmpdir="" parent_dir

  if [[ "$SKIP_GO_INSTALL" -eq 1 ]]; then
    printf 'Go not found and --skip-go-install was set\n' >&2
    return 1
  fi

  os="$(uname -s)"
  arch="$(uname -m)"
  if [[ "$os" != "Linux" || "$arch" != "x86_64" ]]; then
    printf 'Automatic Go install is currently supported only on Linux x86_64 (got %s/%s)\n' "$os" "$arch" >&2
    return 1
  fi

  if ! command -v curl >/dev/null 2>&1; then
    printf 'curl is required to install Go automatically\n' >&2
    return 1
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "Dry-run: would install Go ${GO_VERSION} into $GO_INSTALL_ROOT"
    return 0
  fi

  tmpdir="$(mktemp -d)"
  trap '[[ -n "${tmpdir:-}" ]] && rm -rf "$tmpdir"' RETURN
  parent_dir="$(dirname "$GO_INSTALL_ROOT")"
  url="https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz"

  log "Installing Go ${GO_VERSION} into $GO_INSTALL_ROOT"
  mkdir -p "$parent_dir"
  curl -fsSL "$url" -o "$tmpdir/go.tar.gz"
  rm -rf "$GO_INSTALL_ROOT"
  tar -C "$parent_dir" -xzf "$tmpdir/go.tar.gz"
}

ensure_go_bin() {
  local go_bin
  if go_bin="$(detect_go_bin 2>/dev/null)"; then
    printf '%s\n' "$go_bin"
    return 0
  fi

  install_go_local
  go_bin="$(detect_go_bin)"
  printf '%s\n' "$go_bin"
}

prepare_checkout() {
  if ! command -v git >/dev/null 2>&1; then
    printf 'git is required to install Engram\n' >&2
    return 1
  fi

  if [[ ! -d "$ENGRAM_SRC_DIR/.git" ]]; then
    run mkdir -p "$(dirname "$ENGRAM_SRC_DIR")"
    run git clone "$ENGRAM_REPO_URL" "$ENGRAM_SRC_DIR"
  fi

  run git -C "$ENGRAM_SRC_DIR" fetch --tags origin
  run git -C "$ENGRAM_SRC_DIR" checkout --detach "$ENGRAM_REF"
  run git -C "$ENGRAM_SRC_DIR" reset --hard "$ENGRAM_REF"
  run git -C "$ENGRAM_SRC_DIR" clean -fd
}

apply_patch_if_needed() {
  local patch_file="$KNOWLEDGE_DIR/patches/engram-source-agent.patch"

  if [[ ! -f "$patch_file" ]]; then
    printf 'Patch file not found: %s\n' "$patch_file" >&2
    return 1
  fi

  if git -C "$ENGRAM_SRC_DIR" apply --reverse --check "$patch_file" >/dev/null 2>&1; then
    log "Engram patch already present"
    return 0
  fi

  run git -C "$ENGRAM_SRC_DIR" apply "$patch_file"
}

build_engram() {
  local go_bin="$1"
  local tmp_bin=""
  run mkdir -p "$(dirname "$ENGRAM_BIN")"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "Dry-run: would build Engram with $go_bin into $ENGRAM_BIN"
    return 0
  fi

  log "Building Engram into $ENGRAM_BIN"
  tmp_bin="$(mktemp "${ENGRAM_BIN}.tmp.XXXXXX")"
  trap '[[ -n "${tmp_bin:-}" ]] && rm -f "$tmp_bin"' RETURN
  (cd "$ENGRAM_SRC_DIR" && "$go_bin" build -o "$tmp_bin" ./cmd/engram)
  mv "$tmp_bin" "$ENGRAM_BIN"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --src-dir)
      ENGRAM_SRC_DIR="$2"
      shift 2
      ;;
    --bin)
      ENGRAM_BIN="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --skip-go-install)
      SKIP_GO_INSTALL=1
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

GO_BIN="$(ensure_go_bin)"
log "Using Go binary: $GO_BIN"
prepare_checkout
apply_patch_if_needed
build_engram "$GO_BIN"
log "Engram component installation finished"

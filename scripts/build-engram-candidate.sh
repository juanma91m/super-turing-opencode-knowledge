#!/usr/bin/env bash
# Build only. Never installs over Engram, starts it or opens its database.
set -euo pipefail
umask 077
root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ $# == 1 ]] || { echo 'Usage: build-engram-candidate.sh <absolute-new-binary-path>' >&2; exit 2; }
out="$1"
[[ "$out" = /* && -d "$(dirname -- "$out")" && ! -e "$out" && ! -L "$out" ]] ||
  { echo 'An absolute, unoccupied binary path in an existing directory is required.' >&2; exit 2; }
[[ "$(realpath -m -- "$out")" != "$(realpath -m -- "$HOME/.opencode/bin/engram")" ]] ||
  { echo 'The active Engram path is not a candidate destination.' >&2; exit 2; }
read -r version revision digest toolchain build_id < <(
  python3 -I -B - "$root/KNOWLEDGE-MANIFEST.json" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    pin = json.load(stream)['engramCandidate']
print(*(pin[k] for k in ('upstreamVersion', 'revision', 'sourceSHA256', 'goVersion', 'buildVersion')))
PY
)
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "$revision" =~ ^[a-f0-9]{40}$ &&
   "$digest" =~ ^[a-f0-9]{64}$ && "$toolchain" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ &&
   "$build_id" == "$version"+opencode.* ]] || exit 2
go="${ENGRAM_GO_BIN:-$(command -v go || true)}"
if [[ -z "$go" ]]; then go="$HOME/.local/opt/go/bin/go"; fi
[[ -x "$go" ]] || { echo "Go $toolchain is required." >&2; exit 2; }
stage="$(mktemp -d "$(dirname -- "$out")/.engram-build.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
mkdir -- "$stage/src"
curl -fsSL --max-time 90 "https://codeload.github.com/Gentleman-Programming/engram/tar.gz/$revision" -o "$stage/source.tgz"
printf '%s  %s\n' "$digest" "$stage/source.tgz" | sha256sum -c --status
tar -xzf "$stage/source.tgz" -C "$stage/src" --strip-components=1
(
  cd "$stage/src"
  export GIT_CEILING_DIRECTORIES="$stage"
  git apply --check "$root/patches/engram-v3.7.2-opencode.patch"
  git apply "$root/patches/engram-v3.7.2-opencode.patch"
  GOTOOLCHAIN="go$toolchain" "$go" build -trimpath -ldflags="-X main.version=$build_id" -o "$stage/engram" ./cmd/engram
)
ln -T -- "$stage/engram" "$out"
printf 'Prepared %s (upstream v%s) at %s; not activated.\n' "$build_id" "$version" "$out"

#!/bin/sh
# Install a published Goshikq GitHub Release archive after checking SHA256SUMS.
# No root required. Does not publish or modify a release.
# Usage: sh scripts/install.sh --version v1.0.0
set -eu

version="v1.0.0"
dest=""
repo="goshikavs/goshikq-agent-framework"

while [ $# -gt 0 ]; do
  case "$1" in
    --version) version="$2"; shift 2 ;;
    --dest) dest="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

fail() { echo "$1" >&2; exit 1; }

check_sha() {
  file="$1"
  expected="$2"
  if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$file" | awk '{print $1}')
  elif command -v shasum >/dev/null 2>&1; then
    actual=$(shasum -a 256 "$file" | awk '{print $1}')
  else
    fail "Need sha256sum or shasum to verify the archive."
  fi
  if [ "$actual" != "$expected" ]; then
    fail "SHA256 mismatch for ${file}: expected ${expected} actual ${actual}"
  fi
  echo "SHA256 ok ${actual}"
}

# CI sets these to prove a bad digest is rejected. A normal install does not.
if [ -n "${GOSHIKQ_CHECK_FILE:-}" ]; then
  check_sha "$GOSHIKQ_CHECK_FILE" "${GOSHIKQ_CHECK_EXPECTED:?GOSHIKQ_CHECK_EXPECTED is required}"
  exit 0
fi

os=$(uname -s)
machine=$(uname -m)
case "$os:$machine" in
  Linux:x86_64) platform="linux-amd64"; ext="tar.gz" ;;
  Linux:aarch64|Linux:arm64) platform="linux-arm64"; ext="tar.gz" ;;
  Darwin:x86_64) platform="macos-amd64"; ext="tar.gz" ;;
  Darwin:arm64) platform="macos-arm64"; ext="tar.gz" ;;
  *) fail "Unsupported platform ${os} ${machine}. Supported: Linux x86_64/arm64, macOS x86_64/arm64. Windows: scripts/install.ps1." ;;
esac

case "$version" in
  v*) tag="$version" ;;
  *) tag="v$version" ;;
esac
ver=$(printf '%s' "$tag" | sed 's/^v//')
asset="goshikq-${ver}-${platform}.${ext}"
base="https://github.com/${repo}/releases/download/${tag}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "Downloading ${base}/SHA256SUMS"
curl -fsSL "${base}/SHA256SUMS" -o "${work}/SHA256SUMS"
echo "Downloading ${base}/${asset}"
curl -fsSL "${base}/${asset}" -o "${work}/${asset}"

expected=$(awk -v name="$asset" '$2 == name || $2 == ("./" name) { print $1; exit }' "${work}/SHA256SUMS")
if [ -z "$expected" ]; then
  fail "SHA256SUMS has no entry for ${asset}"
fi
check_sha "${work}/${asset}" "$expected"

if [ -z "$dest" ]; then
  dest="${HOME}/.local/share/goshikq/${tag}"
fi
rm -rf "$dest"
mkdir -p "$dest"
tar -xzf "${work}/${asset}" -C "$dest"
server=$(find "$dest" -type f -name goshikq-server | head -n 1)
if [ -z "$server" ]; then
  fail "Archive did not contain goshikq-server"
fi
bin=$(dirname "$server")
chmod 755 "$bin/goshikq-server" "$bin/goshikq" 2>/dev/null || true
echo "Installed to ${bin}"
echo "Add to PATH for this shell:"
echo "  export PATH=\"${bin}:\$PATH\""
echo "Then run: goshikq-server"
echo "Manual alternative: download ${asset} and SHA256SUMS from ${base} and compare the hash yourself."

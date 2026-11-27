#!/bin/sh
# Install the published v1.0.0 archive, start it, run hello-agent, then install again.
# This is not a from-source cargo build.
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
base="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
stamp=$(od -An -N4 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n' || date +%s)
dest="$base/goshikq-install-smoke-$stamp"
pg="$base/goshikq-install-pg-$stamp"
log="$base/goshikq-install-server.log"
health="$base/goshikq-health.json"
agent_out="$base/goshikq-agent.txt"
bad="$base/goshikq-bad.bin"

rm -rf "$dest" "$pg"
mkdir -p "$base"

echo "INSTALL_SMOKE platform=$(uname -s) $(uname -m)"
sh "$root/scripts/install.sh" --version v1.0.0 --dest "$dest"
server=$(find "$dest" -type f -name goshikq-server | head -n 1)
if [ -z "$server" ]; then
  echo "installer did not produce goshikq-server" >&2
  exit 1
fi
bin=$(dirname "$server")
"$bin/goshikq" --version | tee "$base/goshikq-version.txt"
grep -F "goshikq 1.0.0" "$base/goshikq-version.txt"

printf 'corrupt' > "$bad"
if GOSHIKQ_CHECK_FILE="$bad" GOSHIKQ_CHECK_EXPECTED="0000000000000000000000000000000000000000000000000000000000000000" \
  sh "$root/scripts/install.sh"
then
  echo "checksum mismatch was accepted" >&2
  exit 1
fi
echo "checksum mismatch rejected"

export DATABASE_URL=embedded
export GOSHIKQ_AUTH_MODE=none
export GOSHIKQ_BIND=127.0.0.1:7400
export GOSHIKQ_EMBEDDED_PG_DIR="$pg"
export GOSHIKQ_EMBEDDED_PG_PORT=55470
"$bin/goshikq-server" >"$log" 2>&1 &
pid=$!
cleanup() {
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

ok=0
i=0
while [ "$i" -lt 120 ]; do
  if curl -fsS http://127.0.0.1:7400/health -o "$health"; then
    ok=1
    break
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "goshikq-server exited before /health" >&2
    cat "$log" >&2
    exit 1
  fi
  i=$((i + 1))
  sleep 3
done
if [ "$ok" != 1 ]; then
  echo "goshikq-server did not become healthy" >&2
  cat "$log" >&2
  exit 1
fi
grep -F '"status":"ok"' "$health"
grep -F '"version":"1.0.0"' "$health"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
"$PY" -m pip install -e "$root/sdk/python"
"$PY" "$root/examples/hello-agent/main.py" | tee "$agent_out"
grep -F "verification:  VERIFIED" "$agent_out"

cleanup
trap - EXIT
rm -rf "$dest"
sh "$root/scripts/install.sh" --version v1.0.0 --dest "$dest"
server=$(find "$dest" -type f -name goshikq-server | head -n 1)
bin=$(dirname "$server")
"$bin/goshikq" --version | grep -F "goshikq 1.0.0"
echo INSTALL_SMOKE_PASS

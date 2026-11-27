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
clean="$base/goshikq-installer-clean-$stamp"
rm -rf "$clean"
mkdir -p "$clean"
cp "$root/scripts/install.sh" "$clean/install.sh"
# The installer runs outside the checkout and must not read repository files.
( cd "$clean" && sh ./install.sh --version v1.0.0 --dest "$dest" )
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
  sh "$clean/install.sh"
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
hello=$(find "$dest" -type f -name hello_agent.py | head -n 1)
if [ -z "$hello" ]; then
  echo "installer did not write hello_agent.py" >&2
  exit 1
fi
case "$hello" in
  "$root"/*) echo "quickstart was written inside the repository" >&2; exit 1 ;;
esac
"$PY" "$hello" | tee "$agent_out"
grep -F "verification:  VERIFIED" "$agent_out"

outside="$base/goshikq-py-consumer-$stamp"
"$PY" -m venv "$outside/venv"
"$outside/venv/bin/python" -m pip install -U pip build hatchling
"$outside/venv/bin/python" -m build --wheel --outdir "$outside/dist" "$root/sdk/python"
"$outside/venv/bin/python" -m pip install "$outside"/dist/goshikq_ai-*.whl
cp "$root/examples/quickstart/sdk_hello.py" "$outside/sdk_hello.py"
( cd "$outside" && ./venv/bin/python sdk_hello.py ) | tee "$base/goshikq-sdk-hello.txt"
grep -F "verification:  VERIFIED" "$base/goshikq-sdk-hello.txt"

if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  ts="$base/goshikq-ts-consumer-$stamp"
  mkdir -p "$ts/pack" "$ts/app" "$ts/src"
  # Copy the package out of the monorepo so npm does not see workspace: dependencies.
  cp "$root/sdk/typescript/package.json" "$root/sdk/typescript/tsconfig.json" "$root/sdk/typescript/tsconfig.build.json" "$ts/src/"
  cp -R "$root/sdk/typescript/src" "$ts/src/src"
  if [ -f "$root/sdk/typescript/README.md" ]; then cp "$root/sdk/typescript/README.md" "$ts/src/"; fi
  if [ -f "$root/sdk/typescript/LICENSE" ]; then cp "$root/sdk/typescript/LICENSE" "$ts/src/"; fi
  ( cd "$ts/src" && npm install && npm pack --pack-destination "$ts/pack" )
  tgz=$(find "$ts/pack" -name '*.tgz' | head -n 1)
  printf '%s\n' '{"name":"goshikq-node-consumer","private":true,"type":"module"}' > "$ts/app/package.json"
  ( cd "$ts/app" && npm install "$tgz" )
  cp "$root/examples/quickstart/hello.mjs" "$ts/app/hello.mjs"
  ( cd "$ts/app" && node hello.mjs ) | tee "$base/goshikq-node-hello.txt"
  grep -F "verification:  VERIFIED" "$base/goshikq-node-hello.txt"
else
  echo "TYPESCRIPT_CONSUMER_SKIPPED node or npm missing"
fi

cleanup
trap - EXIT
rm -rf "$dest"
( cd "$clean" && sh ./install.sh --version v1.0.0 --dest "$dest" )
server=$(find "$dest" -type f -name goshikq-server | head -n 1)
bin=$(dirname "$server")
"$bin/goshikq" --version | grep -F "goshikq 1.0.0"
echo INSTALL_SMOKE_PASS

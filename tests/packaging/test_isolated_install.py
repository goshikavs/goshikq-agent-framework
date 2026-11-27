"""Build Python and TypeScript packages and install them outside the repository."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
OUTSIDE = Path(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp")


def _run(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 180) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    merged.pop("PYTHONPATH", None)
    merged["PYTHONNOUSERSITE"] = "1"
    return subprocess.run(cmd, cwd=str(cwd), env=merged, capture_output=True, text=True, timeout=timeout)


def test_python_wheel_and_sdist_isolated_install():
    work = Path(tempfile.mkdtemp(prefix="goshikq-py-sdk-", dir=str(OUTSIDE)))
    try:
        def _py(root: Path) -> Path:
            return root / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")

        builder = work / "builder"
        consumer = work / "consumer"
        venv.create(builder, with_pip=True)
        venv.create(consumer, with_pip=True)
        bpy, py = _py(builder), _py(consumer)
        build = _run([str(bpy), "-m", "pip", "install", "build", "hatchling"], cwd=work, timeout=120)
        assert build.returncode == 0, build.stdout + build.stderr
        packed = _run([str(bpy), "-m", "build", "--wheel", "--outdir", str(work / "dist")], cwd=ROOT / "sdk" / "python")
        assert packed.returncode == 0, packed.stdout + packed.stderr
        wheels = list((work / "dist").glob("goshikq_ai-*.whl"))
        assert wheels, "wheel was not produced"
        inst = _run([str(py), "-m", "pip", "install", str(wheels[0])], cwd=work)
        assert inst.returncode == 0, inst.stdout + inst.stderr
        probe = r"""
import goshikq_ai
from goshikq_ai import Agent, Goal, Runtime, tool, StateSnapshot
from goshikq_ai.models import MockModel, ModelTurn
assert goshikq_ai.__version__ == "1.0.1"
assert hasattr(Agent, '__init__')
assert callable(tool)
from pathlib import Path
assert (Path(goshikq_ai.__file__).parent / "py.typed").is_file()
print('imports-ok', goshikq_ai.__version__)
"""
        r = _run([str(py), "-c", probe], cwd=work)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "imports-ok" in r.stdout
        upgraded = _run([str(py), "-m", "pip", "install", "-U", "pip"], cwd=work, timeout=180)
        assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
        audited = _run([str(py), "-m", "pip", "install", "pip-audit"], cwd=work, timeout=180)
        assert audited.returncode == 0, audited.stdout + audited.stderr
        # goshikq-ai is not on PyPI yet, so audit the installed third-party dependencies.
        freeze = _run([str(py), "-m", "pip", "freeze"], cwd=work)
        assert freeze.returncode == 0, freeze.stdout + freeze.stderr
        reqs = work / "third-party.txt"
        lines = [
            line
            for line in freeze.stdout.splitlines()
            if line and not line.lower().startswith("goshikq-ai") and "==" in line
        ]
        reqs.write_text("\n".join(lines) + "\n", encoding="utf-8")
        audit = _run([str(py), "-m", "pip_audit", "-r", str(reqs)], cwd=work, timeout=180)
        assert audit.returncode == 0, audit.stdout + audit.stderr
        sdist = _run([str(bpy), "-m", "build", "--sdist", "--outdir", str(work / "dist")], cwd=ROOT / "sdk" / "python")
        assert sdist.returncode == 0, sdist.stdout + sdist.stderr
        archives = list((work / "dist").glob("goshikq_ai-*.tar.gz"))
        assert archives, "sdist was not produced"
        sdist_venv = work / "sdist-consumer"
        venv.create(sdist_venv, with_pip=True)
        spy = _py(sdist_venv)
        sinst = _run([str(spy), "-m", "pip", "install", str(archives[0])], cwd=work, timeout=180)
        assert sinst.returncode == 0, sinst.stdout + sinst.stderr
        sprobe = _run([str(spy), "-c", "import goshikq_ai; assert goshikq_ai.__version__ == '1.0.1'; print('sdist-ok')"], cwd=work)
        assert sprobe.returncode == 0, sprobe.stdout + sprobe.stderr
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_python_isolated_runtime_verification():
    """Fresh venv plus a real runtime run. Skips only when no runtime is listening."""
    live = os.environ.get("GOSHIKQ_RUNTIME_URL", "http://127.0.0.1:7400")
    try:
        healthy = httpx.get(f"{live}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        healthy = False
    if not healthy:
        pytest.skip("runtime not reachable for isolated connectivity check")
    work = Path(tempfile.mkdtemp(prefix="goshikq-py-live-", dir=str(OUTSIDE)))
    try:
        def _py(root: Path) -> Path:
            return root / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")

        consumer = work / "consumer"
        venv.create(consumer, with_pip=True)
        py = _py(consumer)
        inst = _run([str(py), "-m", "pip", "install", str(ROOT / "sdk" / "python")], cwd=work, timeout=180)
        assert inst.returncode == 0, inst.stdout + inst.stderr
        script = work / "agent.py"
        script.write_text(
            f"""
from goshikq_ai import Agent, Goal, Runtime, StateSnapshot, tool
from goshikq_ai.models import MockModel, ModelTurn
from goshikq_ai.state import SnapshotContext

store = {{"ok": False}}

@tool(effect="idempotent_write", idempotent=True, risk="low")
def mark():
    store["ok"] = True
    return {{"ok": True}}

class S:
    def snapshot(self, context: SnapshotContext) -> StateSnapshot:
        return StateSnapshot(state=dict(store), version="1", source="mem")
    def version(self, resource_id: str):
        return "1"

agent = Agent(
    name="isolated-py",
    model=MockModel(script=[ModelTurn(tool_calls=[("mark", {{}})]), ModelTurn(content="done")]),
    tools=[mark],
)
goal = Goal(description="ok is true", success=lambda st: st.get("ok") is True)
result = Runtime(agent, endpoint={live!r}, state_provider=S()).run_sync(goal)
print(result.status, result.verification_status, result.run_id)
assert result.verified
""",
            encoding="utf-8",
        )
        run = _run([str(py), str(script)], cwd=work, env={"GOSHIKQ_RUNTIME_URL": live}, timeout=120)
        assert run.returncode == 0, run.stdout + run.stderr
        assert "VERIFIED" in run.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_typescript_tarball_isolated_install():
    bun = shutil.which("bun") or shutil.which("bun.exe")
    home_bun = Path.home() / ".bun" / "bin" / ("bun.exe" if os.name == "nt" else "bun")
    if bun is None and home_bun.exists():
        bun = str(home_bun)
    if bun is None:
        pytest.skip("bun not on PATH")
    work = Path(tempfile.mkdtemp(prefix="goshikq-ts-sdk-", dir=str(OUTSIDE)))
    try:
        installed = _run([bun, "install"], cwd=ROOT / "sdk" / "typescript", timeout=180)
        assert installed.returncode == 0, installed.stdout + installed.stderr
        built = _run([bun, "run", "build"], cwd=ROOT / "sdk" / "typescript", timeout=180)
        assert built.returncode == 0, built.stdout + built.stderr
        packed = _run([bun, "pm", "pack"], cwd=ROOT / "sdk" / "typescript")
        assert packed.returncode == 0, packed.stdout + packed.stderr
        tgz = list((ROOT / "sdk" / "typescript").glob("goshikq-sdk-*.tgz")) + list(
            (ROOT / "sdk" / "typescript").glob("goshikq-ai-sdk-*.tgz")
        )
        assert tgz, "bun pm pack did not produce a tarball"
        dest = work / tgz[0].name
        shutil.move(str(tgz[0]), dest)
        init = _run([bun, "init", "-y"], cwd=work)
        assert init.returncode == 0, init.stdout + init.stderr
        add = _run([bun, "add", str(dest)], cwd=work)
        assert add.returncode == 0, add.stdout + add.stderr
        script = work / "probe.ts"
        script.write_text(
            """
import { Agent, Goal, Runtime, defineTool, MockModel } from "@goshikq/sdk";
if (typeof Agent !== "function") throw new Error("Agent export missing");
if (typeof Goal !== "function") throw new Error("Goal export missing");
if (typeof Runtime !== "function") throw new Error("Runtime export missing");
if (typeof defineTool !== "function") throw new Error("defineTool export missing");
if (typeof MockModel !== "function") throw new Error("MockModel export missing");
console.log("imports-ok");
""",
            encoding="utf-8",
        )
        r = _run([bun, "run", str(script)], cwd=work)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "imports-ok" in r.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_typescript_isolated_runtime_verification():
    """Packed SDK against a running runtime. Skips only when nothing is listening."""
    bun = shutil.which("bun") or shutil.which("bun.exe")
    home_bun = Path.home() / ".bun" / "bin" / ("bun.exe" if os.name == "nt" else "bun")
    if bun is None and home_bun.exists():
        bun = str(home_bun)
    if bun is None:
        pytest.skip("bun not on PATH")
    live = os.environ.get("GOSHIKQ_RUNTIME_URL", "http://127.0.0.1:7400")
    try:
        healthy = httpx.get(f"{live}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        healthy = False
    if not healthy:
        pytest.skip("runtime not reachable for isolated connectivity check")
    work = Path(tempfile.mkdtemp(prefix="goshikq-ts-live-", dir=str(OUTSIDE)))
    try:
        packed = _run([bun, "pm", "pack"], cwd=ROOT / "sdk" / "typescript")
        assert packed.returncode == 0, packed.stdout + packed.stderr
        tgz = list((ROOT / "sdk" / "typescript").glob("goshikq-sdk-*.tgz"))
        assert tgz, "bun pm pack did not produce a tarball"
        dest = work / tgz[0].name
        shutil.move(str(tgz[0]), dest)
        init = _run([bun, "init", "-y"], cwd=work)
        assert init.returncode == 0, init.stdout + init.stderr
        add = _run([bun, "add", str(dest)], cwd=work)
        assert add.returncode == 0, add.stdout + add.stderr
        run_script = work / "agent.ts"
        run_script.write_text(
            """
import { z } from "zod";
import { Agent, Goal, Runtime, defineTool, MockModel, StateSnapshot } from "@goshikq/sdk";
const echo = defineTool({
  name: "echo",
  schema: z.object({ text: z.string() }),
  jsonSchema: { type: "object", properties: { text: { type: "string" } }, required: ["text"], additionalProperties: false },
  effect: "READ_ONLY",
  execute: async ({ text }) => ({ echoed: text }),
});
const agent = new Agent({
  name: "isolated_ts_echo",
  model: new MockModel({
    script: [{ tool_calls: [["echo", { text: "ping" }]] }, { content: "done" }],
  }),
  tools: [echo],
});
const goal = new Goal({
  description: "echo ping",
  success: (s) => s.get("ok") === true,
  maxSteps: 4,
});
const rt = new Runtime(agent, {
  stateProvider: { snapshot: () => new StateSnapshot({ state: { ok: true }, version: "1", source: "live-test" }) },
});
const result = await rt.run(goal, { timeoutMs: 60_000 });
console.log(result.status, result.verificationStatus, result.runId);
if (result.verificationStatus !== "VERIFIED") {
  throw new Error("expected VERIFIED, got " + result.verificationStatus);
}
""",
            encoding="utf-8",
        )
        run = _run([bun, "run", str(run_script)], cwd=work, env={"GOSHIKQ_RUNTIME_URL": live}, timeout=120)
        assert run.returncode == 0, run.stdout + run.stderr
        assert "VERIFIED" in run.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_typescript_node_consumer_imports_javascript():
    """Install the packed tarball in a clean Node project and import it without compiling the consumer."""
    node = shutil.which("node") or shutil.which("node.exe")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    bun = shutil.which("bun") or shutil.which("bun.exe")
    home_bun = Path.home() / ".bun" / "bin" / ("bun.exe" if os.name == "nt" else "bun")
    if bun is None and home_bun.exists():
        bun = str(home_bun)
    if node is None or npm is None or bun is None:
        pytest.skip("node, npm, and bun are required for the Node consumer test")
    work = Path(tempfile.mkdtemp(prefix="goshikq-node-sdk-", dir=str(OUTSIDE)))
    try:
        built = _run([bun, "run", "build"], cwd=ROOT / "sdk" / "typescript", timeout=180)
        assert built.returncode == 0, built.stdout + built.stderr
        packed = _run([npm, "pack", "--pack-destination", str(work)], cwd=ROOT / "sdk" / "typescript")
        assert packed.returncode == 0, packed.stdout + packed.stderr
        tarballs = list(work.glob("goshikq-sdk-*.tgz"))
        assert tarballs, packed.stdout + packed.stderr
        consumer = work / "consumer"
        consumer.mkdir()
        (consumer / "package.json").write_text(
            '{"name":"goshikq-node-consumer","private":true,"type":"module"}',
            encoding="utf-8",
        )
        added = _run([npm, "install", str(tarballs[0])], cwd=consumer, timeout=180)
        assert added.returncode == 0, added.stdout + added.stderr
        probe = consumer / "probe.mjs"
        probe.write_text(
            """
import { Agent, Goal, Runtime, VERSION } from "@goshikq/sdk";
if (VERSION !== "1.0.1") throw new Error("version " + VERSION);
if (typeof Agent !== "function" || typeof Goal !== "function" || typeof Runtime !== "function") {
  throw new Error("missing exports");
}
console.log("node-imports-ok", VERSION);
""",
            encoding="utf-8",
        )
        ran = _run([node, str(probe)], cwd=consumer)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert "node-imports-ok" in ran.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)

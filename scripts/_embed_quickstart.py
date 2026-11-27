"""Insert examples/quickstart/hello_agent.py into the installer scripts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = (ROOT / "examples" / "quickstart" / "hello_agent.py").read_text(encoding="utf-8").replace("\r\n", "\n")
if "END_GOSHIKQ_QUICKSTART" in PY:
    raise SystemExit("quickstart marker collides with the example")

sh = ROOT / "scripts" / "install.sh"
text = sh.read_text(encoding="utf-8").replace("\r\n", "\n")
fn = (
    "write_quickstart() {\n"
    "  cat > \"$1/hello_agent.py\" << 'END_GOSHIKQ_QUICKSTART'\n"
    + PY
    + "END_GOSHIKQ_QUICKSTART\n"
    "}\n\n"
)
if "write_quickstart()" not in text:
    text = text.replace("fail() { echo \"$1\" >&2; exit 1; }\n\n", "fail() { echo \"$1\" >&2; exit 1; }\n\n" + fn)
needle = 'echo "Manual alternative: download ${asset} and SHA256SUMS from ${base} and compare the hash yourself."\n'
insert = (
    'write_quickstart "$bin"\n'
    'echo "First run, after /health is ok. This file does not need the git repository:"\n'
    'echo "  python3 \\"${bin}/hello_agent.py\\""\n'
    + needle
)
if 'write_quickstart "$bin"' not in text:
    if needle not in text:
        raise SystemExit("install.sh anchor missing")
    text = text.replace(needle, insert)
sh.write_bytes(text.encode("utf-8"))

ps1 = ROOT / "scripts" / "install.ps1"
ptext = ps1.read_text(encoding="utf-8").replace("\r\n", "\n")
block = (
    "function Write-GoshikqQuickstart([string]$Directory) {\n"
    "    $quickstart = @'\n"
    + PY.rstrip("\n")
    + "\n'@\n"
    "    $utf8 = New-Object System.Text.UTF8Encoding $false\n"
    "    [System.IO.File]::WriteAllText((Join-Path $Directory 'hello_agent.py'), $quickstart, $utf8)\n"
    "}\n\n"
)
if "function Write-GoshikqQuickstart" not in ptext:
    ptext = ptext.replace("function Fail([string]$Message) {\n", block + "function Fail([string]$Message) {\n")
pneedle = '    Write-Host "Manual alternative: download $asset and SHA256SUMS from $base and compare the hash yourself."\n'
pinsert = (
    "    Write-GoshikqQuickstart $bin\n"
    '    Write-Host "First run, after /health is ok. This file does not need the git repository:"\n'
    "    Write-Host \"  python '$bin\\hello_agent.py'\"\n"
    + pneedle
)
if "Write-GoshikqQuickstart $bin" not in ptext:
    if pneedle not in ptext:
        raise SystemExit("install.ps1 anchor missing")
    ptext = ptext.replace(pneedle, pinsert)
ps1.write_bytes(ptext.encode("utf-8"))
print("embedded", len(PY))

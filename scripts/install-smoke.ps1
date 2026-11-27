# Install the published v1.0.0 Windows archive, start it, run hello-agent, then install again.
# This is not a from-source cargo build.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$base = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$stamp = [guid]::NewGuid().ToString("n")
$dest = Join-Path $base "goshikq-install-smoke-$stamp"
$pg = Join-Path $base "goshikq-install-pg-$stamp"
$log = Join-Path $base "goshikq-install-server.log"
$err = Join-Path $base "goshikq-install-server.err"
$bad = Join-Path $base "goshikq-bad.bin"

function Invoke-Cleanup([System.Diagnostics.Process]$Proc) {
    if ($null -ne $Proc -and -not $Proc.HasExited) {
        taskkill /PID $Proc.Id /T /F | Out-Null
    }
}

if (Test-Path $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
if (Test-Path $pg) { Remove-Item -LiteralPath $pg -Recurse -Force }
Write-Host "INSTALL_SMOKE platform=$([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture)"

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\install.ps1") -Version v1.0.0 -Dest $dest
$cli = Get-ChildItem -Path $dest -Recurse -Filter "goshikq.exe" | Select-Object -First 1
if (-not $cli) { throw "installer did not produce goshikq.exe" }
$version = & $cli.FullName --version
Write-Host $version
if ($version -notmatch "goshikq 1\.0\.0") { throw "unexpected version: $version" }

Set-Content -LiteralPath $bad -Value "corrupt" -NoNewline
$rejected = $false
try {
    & {
        . (Join-Path $root "scripts\install.ps1")
        Test-GoshikqSha256 -Path $bad -Expected ("0" * 64)
    }
} catch {
    if ($_.Exception.Message -match "SHA256 mismatch") { $rejected = $true } else { throw }
}
if (-not $rejected) { throw "checksum mismatch was accepted" }
Write-Host "checksum mismatch rejected"

$env:DATABASE_URL = "embedded"
$env:GOSHIKQ_AUTH_MODE = "none"
$env:GOSHIKQ_BIND = "127.0.0.1:7400"
$env:GOSHIKQ_EMBEDDED_PG_DIR = $pg
$env:GOSHIKQ_EMBEDDED_PG_PORT = "55470"
$server = Get-ChildItem -Path $dest -Recurse -Filter "goshikq-server.exe" | Select-Object -First 1
$proc = Start-Process -FilePath $server.FullName -RedirectStandardOutput $log -RedirectStandardError $err -PassThru -WindowStyle Hidden
try {
    $healthy = $false
    for ($i = 0; $i -lt 120; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:7400/health" -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200 -and $resp.Content -match '"status":"ok"' -and $resp.Content -match '"version":"1.0.0"') {
                $healthy = $true
                Write-Host $resp.Content
                break
            }
        } catch {
            if ($proc.HasExited) {
                Get-Content $log, $err -ErrorAction SilentlyContinue
                throw "goshikq-server exited before /health"
            }
        }
        Start-Sleep -Seconds 3
    }
    if (-not $healthy) {
        Get-Content $log, $err -ErrorAction SilentlyContinue
        throw "goshikq-server did not become healthy"
    }
    python -m pip install -e (Join-Path $root "sdk\python")
    $agentFile = Join-Path $base "goshikq-agent.txt"
    & python (Join-Path $root "examples\hello-agent\main.py") > $agentFile
    if ($LASTEXITCODE -ne 0) { Get-Content $agentFile; throw "hello-agent exited $LASTEXITCODE" }
    $agent = Get-Content $agentFile -Raw
    Write-Host $agent
    if ($agent -notmatch "verification:\s+VERIFIED") { throw "hello-agent did not verify" }
} finally {
    Invoke-Cleanup $proc
}

if (Test-Path $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\install.ps1") -Version v1.0.0 -Dest $dest
$cli = Get-ChildItem -Path $dest -Recurse -Filter "goshikq.exe" | Select-Object -First 1
$version = & $cli.FullName --version
if ($version -notmatch "goshikq 1\.0\.0") { throw "repeat install version: $version" }
Write-Host "INSTALL_SMOKE_PASS"

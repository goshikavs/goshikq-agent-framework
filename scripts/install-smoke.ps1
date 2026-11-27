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
$clean = Join-Path $base "goshikq-installer-clean-$stamp"
if (Test-Path $clean) { Remove-Item -LiteralPath $clean -Recurse -Force }
New-Item -ItemType Directory -Path $clean | Out-Null
Copy-Item (Join-Path $root "scripts\install.ps1") (Join-Path $clean "install.ps1")
# The installer runs outside the checkout and must not read repository files.
Push-Location $clean
try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Version v1.0.0 -Dest $dest
} finally {
    Pop-Location
}
$cli = Get-ChildItem -Path $dest -Recurse -Filter "goshikq.exe" | Select-Object -First 1
if (-not $cli) { throw "installer did not produce goshikq.exe" }
$version = & $cli.FullName --version
Write-Host $version
if ($version -notmatch "goshikq 1\.0\.0") { throw "unexpected version: $version" }

Set-Content -LiteralPath $bad -Value "corrupt" -NoNewline
$rejected = $false
try {
    & {
        . (Join-Path $clean "install.ps1")
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
    $hello = Get-ChildItem -Path $dest -Recurse -Filter "hello_agent.py" | Select-Object -First 1
    if (-not $hello) { throw "installer did not write hello_agent.py" }
    if ($hello.FullName.StartsWith($root)) { throw "quickstart was written inside the repository" }
    $agentFile = Join-Path $base "goshikq-agent.txt"
    & python $hello.FullName > $agentFile
    if ($LASTEXITCODE -ne 0) { Get-Content $agentFile; throw "hello-agent exited $LASTEXITCODE" }
    $agent = Get-Content $agentFile -Raw
    Write-Host $agent
    if ($agent -notmatch "verification:\s+VERIFIED") { throw "hello-agent did not verify" }
    $outside = Join-Path $base "goshikq-py-consumer-$stamp"
    New-Item -ItemType Directory -Path $outside | Out-Null
    & python -m venv (Join-Path $outside "venv")
    $py = Join-Path $outside "venv\Scripts\python.exe"
    & $py -m pip install -U pip build hatchling
    if ($LASTEXITCODE -ne 0) { throw "pip install build failed" }
    & $py -m build --wheel --outdir (Join-Path $outside "dist") (Join-Path $root "sdk\python")
    if ($LASTEXITCODE -ne 0) { throw "wheel build failed" }
    $wheel = Get-ChildItem (Join-Path $outside "dist\goshikq_ai-*.whl") | Select-Object -First 1
    & $py -m pip install $wheel.FullName
    if ($LASTEXITCODE -ne 0) { throw "wheel install failed" }
    Copy-Item (Join-Path $root "examples\quickstart\sdk_hello.py") (Join-Path $outside "sdk_hello.py")
    $sdkOut = Join-Path $base "goshikq-sdk-hello.txt"
    Push-Location $outside
    try { & $py .\sdk_hello.py > $sdkOut } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { Get-Content $sdkOut; throw "sdk hello exited $LASTEXITCODE" }
    $sdkText = Get-Content $sdkOut -Raw
    Write-Host $sdkText
    if ($sdkText -notmatch "verification:\s+VERIFIED") { throw "sdk hello did not verify" }
    $node = Get-Command node -ErrorAction SilentlyContinue
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if ($node -and $npm) {
        $ts = Join-Path $base "goshikq-ts-consumer-$stamp"
        New-Item -ItemType Directory -Path (Join-Path $ts "pack") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $ts "app") -Force | Out-Null
        $src = Join-Path $ts "src"
        New-Item -ItemType Directory -Path $src -Force | Out-Null
        # Copy the package out of the monorepo so npm does not see workspace: dependencies.
        Copy-Item (Join-Path $root "sdk\typescript\package.json") $src
        Copy-Item (Join-Path $root "sdk\typescript\tsconfig.json") $src
        Copy-Item (Join-Path $root "sdk\typescript\tsconfig.build.json") $src
        Copy-Item (Join-Path $root "sdk\typescript\src") (Join-Path $src "src") -Recurse
        foreach ($extra in @("README.md", "LICENSE")) {
            $from = Join-Path $root "sdk\typescript\$extra"
            if (Test-Path $from) { Copy-Item $from $src }
        }
        Push-Location $src
        try {
            & npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install sdk failed" }
            & npm pack --pack-destination (Join-Path $ts "pack")
            if ($LASTEXITCODE -ne 0) { throw "npm pack failed" }
        } finally { Pop-Location }
        $tgz = Get-ChildItem (Join-Path $ts "pack\*.tgz") | Select-Object -First 1
        Set-Content -LiteralPath (Join-Path $ts "app\package.json") -Value '{"name":"goshikq-node-consumer","private":true,"type":"module"}' -Encoding ascii
        Push-Location (Join-Path $ts "app")
        try {
            & npm install $tgz.FullName
            if ($LASTEXITCODE -ne 0) { throw "npm install tarball failed" }
            Copy-Item (Join-Path $root "examples\quickstart\hello.mjs") .\hello.mjs
            $nodeOut = Join-Path $base "goshikq-node-hello.txt"
            & node .\hello.mjs > $nodeOut
            if ($LASTEXITCODE -ne 0) { Get-Content $nodeOut; throw "node hello exited $LASTEXITCODE" }
            $nodeText = Get-Content $nodeOut -Raw
            Write-Host $nodeText
            if ($nodeText -notmatch "verification:\s+VERIFIED") { throw "node hello did not verify" }
        } finally { Pop-Location }
    } else {
        Write-Host "TYPESCRIPT_CONSUMER_SKIPPED node or npm missing"
    }
} finally {
    Invoke-Cleanup $proc
}

if (Test-Path $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
Push-Location $clean
try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Version v1.0.0 -Dest $dest
} finally {
    Pop-Location
}
$cli = Get-ChildItem -Path $dest -Recurse -Filter "goshikq.exe" | Select-Object -First 1
$version = & $cli.FullName --version
if ($version -notmatch "goshikq 1\.0\.0") { throw "repeat install version: $version" }
Write-Host "INSTALL_SMOKE_PASS"

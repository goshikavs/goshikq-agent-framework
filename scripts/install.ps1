# Installs a published Goshikq GitHub Release archive after checking SHA256SUMS.
# Does not request administrator rights. Does not publish or modify a release.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -Version v1.0.0

[CmdletBinding()]
param(
    [string]$Version = "v1.0.0",
    [string]$Dest = ""
)

$ErrorActionPreference = "Stop"
$repo = "goshikavs/goshikq-agent-framework"

function Resolve-GoshikqPlatform([string]$Arch) {
    switch ($Arch) {
        "X64" { return "windows-amd64" }
        "Arm64" { return "windows-arm64" }
        default { throw "Unsupported Windows architecture '$Arch'. Supported: X64, Arm64 (experimental)." }
    }
}

function Test-GoshikqSha256([string]$Path, [string]$Expected) {
    $actual = (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
    $want = $Expected.ToLowerInvariant()
    if ($actual -ne $want) {
        throw "SHA256 mismatch for ${Path}: expected $want actual $actual"
    }
    return $actual
}

# Dot-sourcing loads Test-GoshikqSha256 for tests and does not download a release.
if ($MyInvocation.InvocationName -eq '.') {
    return
}

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

$arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
$os = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
if ($os -notmatch "Windows") {
    Fail "install.ps1 is for Windows. On macOS or Linux run scripts/install.sh."
}
try {
    $platform = Resolve-GoshikqPlatform $arch
} catch {
    Fail $_.Exception.Message
}
$ext = "zip"
if ($platform -eq "windows-arm64") {
    Write-Warning "Windows ARM64 is experimental and is not a supported v1.0 platform."
}

$tag = $Version
if ($tag -notmatch "^v") { $tag = "v$tag" }
$ver = $tag.TrimStart("v")
$asset = "goshikq-$ver-$platform.$ext"
$base = "https://github.com/$repo/releases/download/$tag"
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("goshikq-install-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $work | Out-Null

try {
    $sumsPath = Join-Path $work "SHA256SUMS"
    $archivePath = Join-Path $work $asset
    Write-Host "Downloading $base/SHA256SUMS"
    Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $sumsPath -UseBasicParsing
    Write-Host "Downloading $base/$asset"
    Invoke-WebRequest -Uri "$base/$asset" -OutFile $archivePath -UseBasicParsing

    $line = Get-Content $sumsPath | Where-Object { $_ -match [regex]::Escape($asset) } | Select-Object -First 1
    if (-not $line) { Fail "SHA256SUMS has no entry for $asset" }
    $expected = ($line -split "\s+")[0]
    try {
        $actual = Test-GoshikqSha256 -Path $archivePath -Expected $expected
    } catch {
        Fail $_.Exception.Message
    }
    Write-Host "SHA256 ok $actual"

    if (-not $Dest) {
        $Dest = Join-Path $env:LOCALAPPDATA "goshikq\$tag"
    }
    if (Test-Path $Dest) { Remove-Item -LiteralPath $Dest -Recurse -Force }
    New-Item -ItemType Directory -Path $Dest | Out-Null
    Expand-Archive -Path $archivePath -DestinationPath $Dest -Force
    $server = Get-ChildItem -Path $Dest -Recurse -Filter "goshikq-server.exe" | Select-Object -First 1
    if (-not $server) { Fail "Archive did not contain goshikq-server.exe" }
    $bin = $server.DirectoryName
    Write-Host "Installed to $bin"
    Write-Host "Add to the user PATH for this session:"
    Write-Host "  `$env:PATH = '$bin;' + `$env:PATH"
    Write-Host "Then run: goshikq-server.exe"
    Write-Host "Manual alternative: download $asset and SHA256SUMS from $base and compare the hash yourself."
}
finally {
    if (Test-Path $work) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
}

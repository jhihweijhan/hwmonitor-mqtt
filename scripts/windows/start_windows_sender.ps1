param(
    [string]$ProjectRoot = "",
    [string]$PythonExe = "python",
    [switch]$UseUv,
    [string]$UvExe = "$env:USERPROFILE\.local\bin\uv.exe",
    [string]$UvCacheDir = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
Set-Location $ProjectRoot

if ($UseUv) {
    if (-not (Test-Path $UvExe)) {
        throw "uv executable not found: $UvExe"
    }
    if ([string]::IsNullOrWhiteSpace($UvCacheDir)) {
        $UvCacheDir = Join-Path $ProjectRoot ".uv-cache"
    }
    New-Item -ItemType Directory -Path $UvCacheDir -Force | Out-Null
    $env:UV_CACHE_DIR = $UvCacheDir
    & $UvExe run python -m hwmonitor_mqtt.agents.agent_sender_windows
    exit $LASTEXITCODE
}

& $PythonExe -m hwmonitor_mqtt.agents.agent_sender_windows
exit $LASTEXITCODE

param(
    [string]$TaskName = "HWMonitorMQTTSender",
    [string]$ProjectRoot = "",
    [string]$PythonExe = "python",
    [bool]$UseUv = $true,
    [string]$UvExe = "",
    [string]$UvCacheDir = "",
    [string]$UvPythonInstallDir = "",
    [bool]$EnsureUv = $true,
    [bool]$EnsureDeps = $true,
    [switch]$AtStartup,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)

if ([string]::IsNullOrWhiteSpace($UvCacheDir)) {
    $UvCacheDir = Join-Path $ProjectRoot ".uv-cache"
}
if ([string]::IsNullOrWhiteSpace($UvPythonInstallDir)) {
    $UvPythonInstallDir = Join-Path $ProjectRoot ".uv-python"
}

$StartScript = Join-Path $PSScriptRoot "start_windows_sender.ps1"
if (-not (Test-Path $StartScript)) {
    throw "Cannot find start script: $StartScript"
}

function Resolve-UvExePath {
    param([string]$Candidate)

    if (-not [string]::IsNullOrWhiteSpace($Candidate) -and (Test-Path $Candidate)) {
        return [System.IO.Path]::GetFullPath($Candidate)
    }

    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -and (Test-Path $cmd.Source)) {
        return $cmd.Source
    }

    $known = @(
        "$env:USERPROFILE\.local\bin\uv.exe",
        "$env:USERPROFILE\.cargo\bin\uv.exe",
        "$env:LocalAppData\Programs\uv\uv.exe"
    )
    foreach ($p in $known) {
        if (Test-Path $p) {
            return $p
        }
    }
    return $null
}

function Install-UvIfNeeded {
    $resolved = Resolve-UvExePath -Candidate $UvExe
    if ($resolved) {
        return $resolved
    }
    if (-not $EnsureUv) {
        throw "uv is not available and EnsureUv=false."
    }

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Output "Installing uv via winget..."
        & winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements --silent
        $resolved = Resolve-UvExePath -Candidate $UvExe
        if ($resolved) {
            return $resolved
        }
    }

    Write-Output "Installing uv via official install script..."
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $resolved = Resolve-UvExePath -Candidate $UvExe
    if ($resolved) {
        return $resolved
    }

    throw "Failed to install uv automatically. Please install uv manually and rerun."
}

function Ensure-ProjectDependencies {
    param(
        [string]$ResolvedUvExe,
        [string]$RootPath,
        [string]$CacheDir,
        [string]$PythonDir
    )

    New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
    New-Item -ItemType Directory -Path $PythonDir -Force | Out-Null

    $env:UV_CACHE_DIR = $CacheDir
    $env:UV_PYTHON_INSTALL_DIR = $PythonDir

    Write-Output "Running uv sync in project root..."
    & $ResolvedUvExe sync --project $RootPath
    if ($LASTEXITCODE -ne 0) {
        throw "uv sync failed with exit code $LASTEXITCODE"
    }
}

$resolvedUvExe = $null
if ($UseUv) {
    if ($WhatIf) {
        $resolvedUvExe = Resolve-UvExePath -Candidate $UvExe
        if (-not $resolvedUvExe) {
            $resolvedUvExe = "<uv not found in PATH/known paths>"
        }
    }
    else {
        $resolvedUvExe = Install-UvIfNeeded
        Write-Output "Using uv executable: $resolvedUvExe"

        if ($EnsureDeps) {
            Ensure-ProjectDependencies -ResolvedUvExe $resolvedUvExe -RootPath $ProjectRoot -CacheDir $UvCacheDir -PythonDir $UvPythonInstallDir
        }
    }
}

$argList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$StartScript`"",
    "-ProjectRoot", "`"$ProjectRoot`"",
    "-PythonExe", "`"$PythonExe`"",
    "-UseUv", "$UseUv"
)

if ($UseUv -and $resolvedUvExe) {
    $argList += "-UvExe"
    $argList += "`"$resolvedUvExe`""
    $argList += "-UvCacheDir"
    $argList += "`"$UvCacheDir`""
    $argList += "-UvPythonInstallDir"
    $argList += "`"$UvPythonInstallDir`""
}

if ($WhatIf) {
    Write-Output "WhatIf: would register scheduled task '$TaskName'"
    Write-Output "  ProjectRoot: $ProjectRoot"
    Write-Output "  StartScript: $StartScript"
    Write-Output "  UseUv: $UseUv"
    Write-Output "  UvExe: $resolvedUvExe"
    Write-Output "  UvCacheDir: $UvCacheDir"
    Write-Output "  UvPythonInstallDir: $UvPythonInstallDir"
    Write-Output "  EnsureUv: $EnsureUv"
    Write-Output "  EnsureDeps: $EnsureDeps"
    Write-Output "  AtStartup: $AtStartup"
    Write-Output "  Action: powershell.exe $($argList -join ' ')"
    exit 0
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($argList -join " ")

if ($AtStartup) {
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
}
else {
    $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
    $principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Highest
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings
Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null

Write-Output "Scheduled task '$TaskName' installed."
Write-Output "ProjectRoot: $ProjectRoot"
Write-Output "UseUv: $UseUv"
Write-Output "EnsureUv: $EnsureUv"
Write-Output "EnsureDeps: $EnsureDeps"
Write-Output "AtStartup: $AtStartup"

param(
    [string]$TaskName = "HWMonitorMQTTSender",
    [string]$ProjectRoot = "",
    [string]$PythonExe = "python",
    [switch]$UseUv,
    [string]$UvExe = "$env:USERPROFILE\.local\bin\uv.exe",
    [string]$UvCacheDir = "",
    [switch]$AtStartup,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$StartScript = Join-Path $PSScriptRoot "start_windows_sender.ps1"
if (-not (Test-Path $StartScript)) {
    throw "Cannot find start script: $StartScript"
}

$argList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$StartScript`"",
    "-ProjectRoot", "`"$ProjectRoot`"",
    "-PythonExe", "`"$PythonExe`""
)

if ($UseUv) {
    $argList += "-UseUv"
    $argList += "-UvExe"
    $argList += "`"$UvExe`""
    if (-not [string]::IsNullOrWhiteSpace($UvCacheDir)) {
        $argList += "-UvCacheDir"
        $argList += "`"$UvCacheDir`""
    }
}

if ($WhatIf) {
    Write-Output "WhatIf: would register scheduled task '$TaskName'"
    Write-Output "  ProjectRoot: $ProjectRoot"
    Write-Output "  StartScript: $StartScript"
    Write-Output "  UseUv: $UseUv"
    Write-Output "  UvExe: $UvExe"
    Write-Output "  UvCacheDir: $UvCacheDir"
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
Write-Output "AtStartup: $AtStartup"

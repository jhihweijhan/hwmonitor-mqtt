param(
    [string]$TaskName = "HWMonitorMQTTSender",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

if ($WhatIf) {
    Write-Output "WhatIf: would remove scheduled task '$TaskName' if it exists."
    exit 0
}

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
    Write-Output "Scheduled task '$TaskName' removed."
}
catch {
    if ($_.Exception.Message -match "cannot find the file specified|找不到指定的檔案") {
        Write-Output "Scheduled task '$TaskName' does not exist."
        exit 0
    }
    throw
}

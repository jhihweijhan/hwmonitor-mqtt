# Windows 開機/登入自啟（Task Scheduler）

此流程會在安裝排程時自動完成：

1. 確保 `uv` 可用（找不到就自動安裝）
2. 在專案目錄執行 `uv sync` 安裝相依套件
3. 建立排程，預設使用 `uv run` 啟動 Windows sender

## 安裝排程（預設：登入時啟動）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_windows_sender_task.ps1
```

## 安裝排程（開機啟動，SYSTEM）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_windows_sender_task.ps1 -AtStartup
```

## 只預覽，不實際修改

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_windows_sender_task.ps1 -WhatIf
```

## 常用參數

- `-UseUv $true/$false`：是否使用 uv 啟動（預設 `$true`）
- `-EnsureUv $true/$false`：安裝時是否自動安裝 uv（預設 `$true`）
- `-EnsureDeps $true/$false`：安裝時是否執行 `uv sync`（預設 `$true`）
- `-UvExe <path>`：指定 uv 執行檔
- `-UvCacheDir <path>`：指定 uv cache 目錄（預設 `<ProjectRoot>\.uv-cache`）
- `-UvPythonInstallDir <path>`：指定 uv Python 安裝目錄（預設 `<ProjectRoot>\.uv-python`）
- `-TaskName <name>`：排程名稱（預設 `HWMonitorMQTTSender`）

## 卸載排程

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\uninstall_windows_sender_task.ps1
```

## 驗證排程

```powershell
Get-ScheduledTask -TaskName HWMonitorMQTTSender
Start-ScheduledTask -TaskName HWMonitorMQTTSender
Get-ScheduledTaskInfo -TaskName HWMonitorMQTTSender
```

# Windows 開機自啟（Task Scheduler）

本文件提供 Windows 端 `agent_sender_windows.py` 的自動啟動方式。  
目標是開機或登入後自動啟動 sender，並由 sender 自動帶起 LibreHardwareMonitor（若 `LHM_AUTOSTART=1`）。

## 前置條件

1. 已安裝 Python 與專案相依套件（含 `psutil`, `paho-mqtt`, `python-dotenv`, `wmi`）。
2. `.env` 已設定 `BROKER_HOST` 等 MQTT 參數。
3. Windows 機器可執行 `powershell.exe` 與排程工作。

## 腳本位置

- `scripts/windows/start_windows_sender.ps1`
- `scripts/windows/install_windows_sender_task.ps1`
- `scripts/windows/uninstall_windows_sender_task.ps1`

## 安裝排程（登入啟動）

在專案根目錄執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_windows_sender_task.ps1
```

## 安裝排程（開機啟動，SYSTEM）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_windows_sender_task.ps1 -AtStartup
```

## 使用 uv 啟動 sender（可選）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_windows_sender_task.ps1 -UseUv
```

若 `uv` 不在預設路徑，可加上：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_windows_sender_task.ps1 -UseUv -UvExe "C:\path\to\uv.exe"
```

若要自訂 `uv` cache 位置：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_windows_sender_task.ps1 -UseUv -UvCacheDir "D:\uv-cache"
```

## 卸載排程

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\uninstall_windows_sender_task.ps1
```

## 驗證排程狀態

```powershell
Get-ScheduledTask -TaskName HWMonitorMQTTSender
```

## 常用參數

- `-TaskName`: 排程名稱（預設 `HWMonitorMQTTSender`）
- `-ProjectRoot`: 專案根目錄（預設自動推導）
- `-PythonExe`: Python 執行檔（預設 `python`）
- `-UseUv`: 以 `uv run` 啟動 sender
- `-UvExe`: `uv` 執行檔路徑
- `-UvCacheDir`: `uv` cache 目錄（未指定時預設 `<ProjectRoot>\.uv-cache`）
- `-AtStartup`: 改為開機啟動（SYSTEM）
- `-WhatIf`: 只顯示將執行的設定，不實際註冊/移除

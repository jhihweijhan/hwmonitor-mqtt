# hwmonitor-mqtt

[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MQTT](https://img.shields.io/badge/MQTT-Realtime-FF6F00)](https://mqtt.org/)
[![License](https://img.shields.io/badge/License-GPLv3-2ea44f)](./LICENSE)

把硬體監控變成「即時可視化資料流」：
- Agent 低負擔採集 CPU/RAM/Disk/Network/GPU/Temperature。
- MQTT 做資料總線，支援多主機擴充。
- Web 與本機 Viewer 即時呈現，不必重後端。

## 為什麼值得用

- 低門檻：`docker compose` 一鍵起服務。
- 低耦合：採集、訊息、顯示分離。
- 可擴展：同時支援 Linux / Windows Agent 與 ESP 輕量 payload。
- 可維護：文件與 Python 檔案已分層，路徑更清楚。

## 架構圖（含圖例）

```mermaid
flowchart LR
    A[Agent Sender\nLinux/Windows] -->|MQTT publish| B[(MQTT Broker)]
    B -->|WebSocket subscribe| C[Web Monitor]
    B -->|MQTT subscribe| D[TUI / Pygame Viewer]

    classDef agent fill:#e3f2fd,stroke:#1e88e5,color:#0d47a1
    classDef broker fill:#fff8e1,stroke:#f9a825,color:#e65100
    classDef view fill:#e8f5e9,stroke:#43a047,color:#1b5e20
    class A agent
    class B broker
    class C,D view
```

### 圖例說明

- 藍色節點：資料生產者（Agent）
- 黃色節點：訊息中樞（Broker）
- 綠色節點：資料消費者（Web/TUI/Pygame）
- 箭頭標籤：通訊方式（`MQTT publish` / `subscribe` / `WebSocket`）

## Viewer 預覽

### PyGame Viewer

![PyGame Viewer Preview](./docs/assets/previews/pygame-viewer-preview.svg)

### TUI Viewer

![TUI Viewer Preview](./docs/assets/previews/tui-viewer-preview.svg)

## 專案結構

```text
.
├─ hwmonitor_mqtt/
│  ├─ agents/
│  │  ├─ agent_sender_async.py
│  │  └─ agent_sender_windows.py
│  └─ viewers/
│     ├─ pygame_viewer.py
│     └─ tui_viewer.py
├─ wifi_portal/
├─ docs/
│  ├─ getting-started/
│  ├─ architecture/
│  ├─ deployment/
│  ├─ configuration/
│  ├─ hardware/
│  └─ troubleshooting/
├─ tests/
└─ docker-compose.yml
```

> 主要執行入口已統一到 `hwmonitor_mqtt/` 套件路徑。

## 快速開始

### 1. 設定環境

```bash
cp .env.example .env
```

至少設定：`BROKER_HOST`、`BROKER_PORT`、`MQTT_USER`、`MQTT_PASS`。

### 2. 啟動模式

只啟動 Agent：

```bash
docker compose --profile agent up -d
```

完整模式（Agent + Broker + Web）：

```bash
docker compose --profile full up -d
```

ESP 輕量模式：

```bash
docker compose --profile esp-agent up -d
```

### 3. 觀察狀態

```bash
docker compose ps
docker compose logs -f
```

Web 介面預設：`http://localhost:8088`

## 文件入口

- [文件中心](./docs/README.md)
- [快速開始](./docs/getting-started/quickstart.md)
- [部署說明](./docs/deployment/docker-profiles.md)
- [環境變數](./docs/configuration/env-vars.md)
- [系統架構](./docs/architecture/system-overview.md)
- [硬體設定](./docs/hardware/README.md)
- [疑難排解](./docs/troubleshooting/common-issues.md)

## Python 開發

本專案有 `pyproject.toml`，建議使用 `uv`：

```bash
uv sync
uv run pytest -q
```

## 授權

本專案採用 `GNU GPL v3.0`。  
可商用，但散佈修改版或衍生作品時，需依 GPL 條款提供對應原始碼。詳見 [LICENSE](./LICENSE)。

## Windows Sender 安裝與注意事項

建議使用「系統管理員」PowerShell 執行以下步驟。

### 1. 準備 `.env`

```powershell
Copy-Item .env.example .env
```

請至少確認：
- `BROKER_HOST`
- `BROKER_PORT`
- `MQTT_USER`
- `MQTT_PASS`

### 2. 安裝 Windows sender 排程（建議開機自動啟動）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_windows_sender_task.ps1 -AtStartup
```

說明：
- 會優先使用 `uv`（若可用），並執行 `uv sync` 安裝依賴。
- 會自動檢查/安裝 LibreHardwareMonitor 到 `third_party/librehardwaremonitor`（預設啟用）。
- `-AtStartup` 會用 `SYSTEM` 建立排程，通常可避免 UAC 導致的 LHM 啟動問題。

### 3. 啟動與檢查

```powershell
Start-ScheduledTask -TaskName HWMonitorMQTTSender
Get-ScheduledTaskInfo -TaskName HWMonitorMQTTSender
```

### 4. 重要注意事項

- 不要同時啟動多個 sender 實例，否則 viewer 可能出現 CPU/GPU 資料跳動或 `NA` 閃爍。
- 若看到 `Access is denied (0x80070005)`，請改用系統管理員 PowerShell。
- 若看到 `WinError 740`，代表目前權限不足以啟動 LibreHardwareMonitor。
- Windows sender 會先嘗試 WMI；若 WMI 回傳空資料，會改用 `LibreHardwareMonitorLib.dll`（`pythonnet`）讀取感測器，並保留 `nvidia-smi` fallback。
- 安裝後通常不需要重開機。

### 5. 清理重複 sender（必要時）

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'hwmonitor_mqtt\.agents\.agent_sender_(windows|async)' -or $_.CommandLine -match 'start_windows_sender\.ps1' } |
  Select-Object ProcessId, Name, CommandLine

# 確認後再停止
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'hwmonitor_mqtt\.agents\.agent_sender_(windows|async)' -or $_.CommandLine -match 'start_windows_sender\.ps1' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

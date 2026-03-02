# Windows Sender 運作時序圖

本文描述 `hwmonitor_mqtt/agents/agent_sender_windows.py` 在 Windows 上的啟動、資料收集與發佈流程。

## 主要組件

- `Task Scheduler`：排程觸發 sender 啟動。
- `start_windows_sender.ps1`：啟動入口，負責 `uv run` 或直接 `python -m`。
- `uv` / `.venv`：Python 環境與依賴管理。
- `agent_sender_windows.py`：核心 sender，負責收集與發佈。
- `python-dotenv`：載入 `.env`。
- `psutil`：CPU / Memory / Disk / Network 基礎指標。
- `wmi` + `LibreHardwareMonitor.exe`：WMI 感測資料來源（`root/LibreHardwareMonitor`）。
- `pythonnet` + `LibreHardwareMonitorLib.dll`：WMI 失敗時的 in-process 感測 fallback。
- `nvidia-smi`：NVIDIA GPU fallback。
- `MQTT Broker`：接收 sender 發佈的 metrics。
- `Viewers`（Web / Pygame / TUI）：訂閱並顯示 metrics。

## 啟動時序

```mermaid
sequenceDiagram
    autonumber
    participant TS as Task Scheduler
    participant PS as start_windows_sender.ps1
    participant UV as uv / python
    participant S as agent_sender_windows.py
    participant ENV as .env (dotenv)
    participant LHM as LibreHardwareMonitor.exe
    participant WMI as root/LibreHardwareMonitor
    participant DLL as LibreHardwareMonitorLib.dll (pythonnet)
    participant MQTT as MQTT Broker

    TS->>PS: 觸發排程 (AtStartup / AtLogon)
    PS->>UV: 啟動 `uv run ... agent_sender_windows`
    UV->>S: 啟動 Python sender
    S->>ENV: 載入 `.env`
    S->>MQTT: connect_async + loop_start

    alt WMI 可用
        S->>LHM: ensure_ready() / autostart (可選)
        LHM-->>WMI: 提供 Sensor Namespace
    else WMI 失敗或空資料
        S->>DLL: 初始化 in-process collector
        DLL-->>S: 可直接讀取硬體 Sensors
    end
```

## 運行時序（輪詢與發佈）

```mermaid
sequenceDiagram
    autonumber
    participant S as agent_sender_windows.py
    participant PSUTIL as psutil
    participant WMI as LHM WMI
    participant DLL as LHM DLL collector
    participant NSMI as nvidia-smi
    participant MQTT as MQTT Broker
    participant V as Viewers

    loop 每 1 秒
        S->>PSUTIL: CPU / Memory / System
    end

    loop 每 3 秒
        S->>PSUTIL: Disk I/O
    end

    loop 每 1 秒
        S->>PSUTIL: Network I/O
    end

    loop 每 10 秒
        S->>WMI: 讀取 Sensors
        alt WMI 回傳空
            S->>DLL: 讀取 Sensors
        end
        S->>S: update_lhm_metrics() 合併 CPU/GPU/溫度
        S->>NSMI: GPU fallback (NVIDIA)
        S->>S: 保留 last-known 值，避免 NA 閃爍
    end

    loop 每 PUBLISH_INTERVAL_SEC
        S->>S: build payload (full / esp)
        S->>MQTT: publish sys/agents/{host}/metrics
        MQTT-->>V: subscribe/update
    end
```

## 互動重點

- Windows sender 使用「多來源合併」：`WMI -> DLL fallback -> nvidia-smi fallback`。
- 發佈前會保留前一輪有效值，避免單次輪詢缺值導致 Viewer 閃爍 `NA`。
- 多 GPU 以穩定裝置識別合併，降低部分感測缺值時遺失次要 GPU 的機率。

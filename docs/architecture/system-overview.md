# 系統架構

## 核心資料流

1. Agent 收集 CPU / RAM / Disk / Network / Temperature / GPU。
2. Agent 發送 JSON 到 MQTT Topic。
3. Web 端透過 WebSocket 訂閱 MQTT 並即時顯示。

## Python 程式結構

```text
hwmonitor_mqtt/
├─ agents/
│  ├─ agent_sender_async.py
│  └─ agent_sender_windows.py
└─ viewers/
   ├─ pygame_viewer.py
   └─ tui_viewer.py
```

## 設計重點

- `agents/` 專注資料收集與發送。
- `viewers/` 專注顯示與互動。
- 根目錄保留 shim（同名 `.py`）以維持舊指令與測試相容。

## Windows Sender 行為

- `agent_sender_windows.py` 會先用 `psutil` 蒐集 CPU/RAM/Disk/Network。
- 若可用，會透過 `root/LibreHardwareMonitor` WMI provider 補齊 CPU 溫度/時脈、儲存裝置溫度與 GPU 資料。
- 支援 `SENDER_PROFILE=full|esp`，payload schema 與 `agent_sender_async.py` 對齊（含 `gpu` + `gpus`）。
- 可使用 `LHM_AUTOSTART=1` 在 sender 啟動時自動拉起 LibreHardwareMonitor。

## Windows 時序

- 詳細流程請見：[Windows Sender 運作時序圖](./windows-runtime-sequence.md)

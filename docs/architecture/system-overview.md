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

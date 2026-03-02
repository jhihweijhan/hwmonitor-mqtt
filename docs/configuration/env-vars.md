# 環境變數

## MQTT 連線

- `BROKER_HOST`
- `BROKER_PORT`
- `MQTT_USER`
- `MQTT_PASS`

## 發送策略

- `SENDER_PROFILE`: `full` 或 `esp`
- `PUBLISH_INTERVAL_SEC`
- `ESP_MIN_PUBLISH_INTERVAL_SEC`
- `ESP_HEARTBEAT_INTERVAL_SEC`

## Web

- `WEB_PORT`

## 建議

- 生產環境請用強密碼並限制 Broker 網段。
- 先在單機驗證 topic，再擴展到多主機。

## Windows Sender 附加參數

- `LHM_PATH`: LibreHardwareMonitor.exe 路徑（可選）
- `LHM_AUTOSTART`: `1/0`，啟用 sender 自動啟動 LibreHardwareMonitor（預設 `1`）
- `LHM_STARTUP_TIMEOUT_SEC`: 等待 WMI namespace 就緒秒數（預設 `15`）
- `LHM_KILL_ON_EXIT`: `1/0`，sender 結束時是否關閉自己啟動的 LibreHardwareMonitor（預設 `1`）
- `SENDER_PROFILE`: `full` 或 `esp`（Windows sender 也支援）
- `PUBLISH_INTERVAL_SEC`: 發送間隔（秒）
- `ESP_MIN_PUBLISH_INTERVAL_SEC`: esp 模式最小發送間隔（秒）
- `ESP_HEARTBEAT_INTERVAL_SEC`: esp 模式心跳發送間隔（秒）
- `ESP_CPU_DELTA`, `ESP_RAM_DELTA`, `ESP_TEMP_DELTA`: esp 模式變化閾值
- `ESP_NET_DELTA_BYTES`, `ESP_DISK_DELTA_BYTES`, `ESP_GPU_DELTA`: esp 模式 I/O 與 GPU 閾值

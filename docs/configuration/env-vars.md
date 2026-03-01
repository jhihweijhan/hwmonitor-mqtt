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

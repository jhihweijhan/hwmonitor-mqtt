# 快速開始

## 1. 準備環境

- Docker
- Docker Compose（使用 `docker compose` 指令）

## 2. 設定 `.env`

```bash
cp .env.example .env
```

最少需設定：

- `BROKER_HOST`
- `BROKER_PORT`
- `MQTT_USER`
- `MQTT_PASS`

## 3. 啟動服務

只跑 Agent：

```bash
docker compose --profile agent up -d
```

完整模式（Agent + Broker + Web）：

```bash
docker compose --profile full up -d
```

## 4. 觀察資料

- Web UI：`http://localhost:8088`
- 日誌：`docker compose logs -f`

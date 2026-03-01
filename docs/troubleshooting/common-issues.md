# 疑難排解

## Agent 沒有送資料

檢查：

```bash
docker compose logs -f sys_agent
```

確認：

- `.env` 的 Broker 參數正確
- Broker 可連通（IP/防火牆/Port）

## Web 沒有更新

檢查：

- `web_monitor` 是否啟動
- Browser Console 是否有 WebSocket 錯誤

## Windows 讀不到硬體資訊

- LibreHardwareMonitor 必須以管理員權限執行
- 必須啟用 WMI Provider

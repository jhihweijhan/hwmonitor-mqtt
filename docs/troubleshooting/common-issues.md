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

## Windows Sender 自動啟動 LibreHardwareMonitor 失敗

檢查項目：

- `LHM_PATH` 是否指向有效的 `LibreHardwareMonitor.exe`
- 帳號是否有權限啟動外部程式
- 防毒/企業防護是否阻擋 LHM 啟動
- `LHM_STARTUP_TIMEOUT_SEC` 是否太短
- LHM 中是否啟用 WMI Provider（`root/LibreHardwareMonitor`）

建議：

- 先手動啟動 LHM 並確認 WMI namespace 可讀，再切回 `LHM_AUTOSTART=1`
- 若 sender 啟動了 LHM，預設會在 sender 結束時關閉（`LHM_KILL_ON_EXIT=1`）

## Windows GPU 仍為空值（WinError 740）

若日誌出現 `Failed to start LibreHardwareMonitor: [WinError 740]`，代表目前權限不足以啟動 LHM。

建議：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\uninstall_windows_sender_task.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_windows_sender_task.ps1 -AtStartup
```

`-AtStartup` 會以 `SYSTEM` 建立排程，通常可避免 UAC 導致的 LHM 啟動失敗。

另外，Windows sender 已加入 NVIDIA `nvidia-smi` fallback；若 LHM/WMI 暫不可用，仍可回報基本 GPU 指標。

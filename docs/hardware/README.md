# 硬體文件中心

本區整理與硬體能力直接相關的操作文件，分成 `GPU` 與 `Display` 兩大主題。

## 結構

```text
docs/hardware/
├─ gpu/
│  └─ requirements.md
├─ display/
│  └─ raspberrypi-3.5inch.md
```

## 文件入口

- GPU 需求與能力矩陣：[`gpu/requirements.md`](./gpu/requirements.md)
- Raspberry Pi 3.5 吋顯示器設定：[`display/raspberrypi-3.5inch.md`](./display/raspberrypi-3.5inch.md)

## 關聯建議

1. 若你是要讓 Viewer 正確顯示 GPU 資訊：先讀 GPU 文件，再讀顯示器文件。
2. 若你是要在小螢幕部署（Pi 3.5 吋）：先讀顯示器文件，再回頭確認 GPU 工具需求。

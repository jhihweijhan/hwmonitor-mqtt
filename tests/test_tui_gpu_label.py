import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hwmonitor_mqtt.viewers.tui_viewer import DeviceDisplay


def _make_data(label):
    return {
        "cpu": {"percent_total": 12.3},
        "memory": {"ram": {"percent": 34.5}},
        "gpus": [
            {"temperature_celsius": 60.0, "temperature_label": label},
        ],
        "temperatures": {"k10temp": [{"current": 40.0}]},
        "network_io": {"per_nic": {}},
        "disk_io": {},
    }


def test_gpu_label_no_gpu_prefix():
    display = DeviceDisplay(0)
    display.metrics_label.update = lambda s: setattr(display.metrics_label, "_last", s)
    display.watch_device_data(_make_data("MEM"))
    renderable = str(display.metrics_label._last)
    assert "GPU" not in renderable
    assert "MEM" in renderable

import io
import importlib
import sys
import types
import subprocess
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _import_agent_sender_async():
    class DummyInfo:
        rc = 0

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def username_pw_set(self, *args, **kwargs):
            pass

        def loop_start(self, *args, **kwargs):
            pass

        def connect(self, *args, **kwargs):
            pass

        def publish(self, *args, **kwargs):
            return DummyInfo()

    class DummyCallbackAPIVersion:
        VERSION2 = object()

    client_module = types.ModuleType("paho.mqtt.client")
    client_module.Client = DummyClient
    client_module.CallbackAPIVersion = DummyCallbackAPIVersion

    mqtt_module = types.ModuleType("paho.mqtt")
    mqtt_module.client = client_module

    paho_module = types.ModuleType("paho")

    sys.modules["paho"] = paho_module
    sys.modules["paho.mqtt"] = mqtt_module
    sys.modules["paho.mqtt.client"] = client_module

    if "agent_sender_async" in sys.modules:
        del sys.modules["agent_sender_async"]

    return importlib.import_module("agent_sender_async")


def test_get_gpu_block_handles_multiple_drm_cards(monkeypatch):
    module = _import_agent_sender_async()

    class DummyResult:
        def __init__(self):
            self.returncode = 1
            self.stdout = ""

    def fake_run(*args, **kwargs):
        return DummyResult()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(module.psutil, "sensors_temperatures", lambda *args, **kwargs: {})

    card0 = "/sys/class/drm/card0"
    card1 = "/sys/class/drm/card1"

    def fake_glob(pattern):
        if pattern == "/sys/class/drm/card*":
            return [card0, card1]
        if pattern == f"{card0}/device/hwmon/hwmon*/temp*_input":
            return [
                f"{card0}/device/hwmon/hwmon0/temp1_input",
                f"{card0}/device/hwmon/hwmon0/temp2_input",
                f"{card0}/device/hwmon/hwmon0/temp3_input",
            ]
        if pattern == f"{card1}/device/hwmon/hwmon*/temp*_input":
            return [f"{card1}/device/hwmon/hwmon1/temp1_input"]
        if pattern == f"{card0}/hwmon/hwmon*/temp*_input":
            return []
        if pattern == f"{card1}/hwmon/hwmon*/temp*_input":
            return []
        return []

    monkeypatch.setattr(glob, "glob", fake_glob)

    file_map = {
        f"{card0}/device/vendor": "0x1002\n",
        f"{card1}/device/vendor": "0x8086\n",
        f"{card0}/device/gpu_busy_percent": "55\n",
        f"{card1}/engine/rcs0/busy_percent": "7\n",
        f"{card0}/device/hwmon/hwmon0/temp1_input": "37000\n",
        f"{card0}/device/hwmon/hwmon0/temp1_label": "edge\n",
        f"{card0}/device/hwmon/hwmon0/temp2_input": "39000\n",
        f"{card0}/device/hwmon/hwmon0/temp2_label": "junction\n",
        f"{card0}/device/hwmon/hwmon0/temp3_input": "60000\n",
        f"{card0}/device/hwmon/hwmon0/temp3_label": "mem\n",
        f"{card1}/device/hwmon/hwmon1/temp1_input": "42000\n",
        f"{card1}/device/hwmon/hwmon1/temp1_label": "core\n",
    }

    def fake_open(path, *args, **kwargs):
        key = str(path)
        if key in file_map:
            return io.StringIO(file_map[key])
        raise FileNotFoundError(key)

    monkeypatch.setattr("builtins.open", fake_open)

    gpus = module.get_gpu_block()

    assert len(gpus) == 2
    assert gpus[0]["usage_percent"] == 55.0
    assert gpus[0]["temperature_celsius"] == 60.0
    assert gpus[0]["temperature_label"] == "MEM"
    assert gpus[1]["usage_percent"] == 7.0
    assert gpus[1]["temperature_celsius"] == 42.0
    assert gpus[1]["temperature_label"] == "COR"

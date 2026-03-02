#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Async System Monitor for Windows (Multi-rate MQTT sender)
- Uses psutil for CPU/MEM/NET/DISK baseline metrics.
- Uses LibreHardwareMonitor WMI for CPU temperatures/clocks, storage temperatures, and GPU metrics.
- Supports full/esp sender profiles compatible with agent_sender_async payloads.
"""

import asyncio
import json
import os
import platform
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psutil
    from dotenv import load_dotenv
    from paho.mqtt import client as mqtt
except ImportError as e:
    print(f"A required package is not installed: {e}")
    print("Please install dependencies first.")
    raise SystemExit(1)

try:
    import wmi
except ImportError:
    wmi = None

load_dotenv()


# ===== Helpers =====
def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


# ===== MQTT CONFIG =====
BROKER_HOST = os.getenv("BROKER_HOST", "").strip()
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "mqtter")
MQTT_PASS = os.getenv("MQTT_PASS", "seven777")
HOSTNAME = socket.gethostname()
TOPIC = f"sys/agents/{HOSTNAME}/metrics"

SENDER_PROFILE = os.getenv("SENDER_PROFILE", "full").strip().lower()
if SENDER_PROFILE not in {"full", "esp"}:
    print(f"Unknown SENDER_PROFILE='{SENDER_PROFILE}', fallback to full")
    SENDER_PROFILE = "full"

PUBLISH_INTERVAL_SEC = _env_float("PUBLISH_INTERVAL_SEC", 1.0)
ESP_MIN_PUBLISH_INTERVAL_SEC = _env_float("ESP_MIN_PUBLISH_INTERVAL_SEC", 2.0)
ESP_HEARTBEAT_INTERVAL_SEC = _env_float("ESP_HEARTBEAT_INTERVAL_SEC", 10.0)
ESP_CPU_DELTA = _env_float("ESP_CPU_DELTA", 3.0)
ESP_RAM_DELTA = _env_float("ESP_RAM_DELTA", 2.0)
ESP_TEMP_DELTA = _env_float("ESP_TEMP_DELTA", 1.0)
ESP_NET_DELTA_BYTES = _env_float("ESP_NET_DELTA_BYTES", 16384.0)
ESP_DISK_DELTA_BYTES = _env_float("ESP_DISK_DELTA_BYTES", 65536.0)
ESP_GPU_DELTA = _env_float("ESP_GPU_DELTA", 3.0)

# ===== LibreHardwareMonitor Process Config =====
LHM_PATH = os.getenv("LHM_PATH", "").strip()
LHM_AUTOSTART = _env_bool("LHM_AUTOSTART", True)
LHM_STARTUP_TIMEOUT_SEC = _env_float("LHM_STARTUP_TIMEOUT_SEC", 15.0)
LHM_KILL_ON_EXIT = _env_bool("LHM_KILL_ON_EXIT", True)


class LHMProcessManager:
    """Manages LibreHardwareMonitor process lifecycle for WMI data collection."""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.started_by_agent = False

    @staticmethod
    def _namespace_available() -> bool:
        if wmi is None:
            return False
        try:
            wmi.WMI(namespace="root/LibreHardwareMonitor")
            return True
        except Exception:
            return False

    @staticmethod
    def _candidate_paths() -> List[Path]:
        candidates: List[Path] = []
        if LHM_PATH:
            candidates.append(Path(LHM_PATH))

        program_files = os.getenv("PROGRAMFILES", "")
        program_files_x86 = os.getenv("PROGRAMFILES(X86)", "")
        local_appdata = os.getenv("LOCALAPPDATA", "")

        if program_files:
            candidates.append(Path(program_files) / "LibreHardwareMonitor" / "LibreHardwareMonitor.exe")
        if program_files_x86:
            candidates.append(Path(program_files_x86) / "LibreHardwareMonitor" / "LibreHardwareMonitor.exe")
        if local_appdata:
            candidates.append(Path(local_appdata) / "LibreHardwareMonitor" / "LibreHardwareMonitor.exe")

        project_root = Path(__file__).resolve().parents[2]
        candidates.append(project_root / "third_party" / "librehardwaremonitor" / "LibreHardwareMonitor.exe")

        return candidates

    @classmethod
    def _resolve_executable(cls) -> Optional[Path]:
        for path in cls._candidate_paths():
            if path and path.exists() and path.is_file():
                return path
        return None

    def _wait_for_namespace(self, timeout_sec: float) -> bool:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self._namespace_available():
                return True
            time.sleep(0.5)
        return self._namespace_available()

    def ensure_ready(self) -> bool:
        if self._namespace_available():
            return True

        if not LHM_AUTOSTART:
            print("LHM namespace is unavailable and LHM_AUTOSTART=0.")
            return False

        exe = self._resolve_executable()
        if exe is None:
            print("LHM executable not found. Set LHM_PATH or install LibreHardwareMonitor.")
            return False

        try:
            self.process = subprocess.Popen(
                [str(exe)],
                cwd=str(exe.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.started_by_agent = True
            print(f"Started LibreHardwareMonitor: {exe}")
        except Exception as e:
            print(f"Failed to start LibreHardwareMonitor: {e}")
            return False

        if self._wait_for_namespace(LHM_STARTUP_TIMEOUT_SEC):
            return True

        print("Timed out waiting for WMI namespace root/LibreHardwareMonitor.")
        return False

    def stop(self):
        if not (self.started_by_agent and LHM_KILL_ON_EXIT and self.process):
            return
        if self.process.poll() is not None:
            return

        try:
            self.process.terminate()
            self.process.wait(timeout=5)
            print("Stopped LibreHardwareMonitor process.")
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass


# ===== MQTT Client =====
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"agent-{HOSTNAME}")
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

mqtt_stats = {
    "publish_ok": 0,
    "publish_err": 0,
    "last_publish_rc": None,
    "reconnects": 0,
    "is_connected": False,
    "last_error": None,
}


def on_connect(client, userdata, connect_flags, reason_code, properties=None):
    mqtt_stats["is_connected"] = reason_code == 0
    if reason_code == 0:
        print(f"MQTT connected to {BROKER_HOST}:{BROKER_PORT}")
        mqtt_stats["last_error"] = None
    else:
        print(f"MQTT connect failed: reason_code={reason_code}")
        mqtt_stats["last_error"] = f"Connect failed: {reason_code}"


mqtt_client.on_connect = on_connect


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    mqtt_stats["is_connected"] = False
    mqtt_stats["last_error"] = f"Disconnected: {reason_code}"


mqtt_client.on_disconnect = on_disconnect


# ===== GLOBAL STATE =====
metrics: Dict[str, Any] = {
    "cpu": None,
    "memory": None,
    "disk_io": None,
    "temperatures": None,
    "network_io": None,
    "system": None,
    "gpu": [],
}

_lhm_manager = LHMProcessManager()
_last_esp_signature: Optional[Dict[str, float]] = None
_last_esp_publish_monotonic = 0.0


# ===== CPU / MEM / SYSTEM =====
def get_cpu_base_block() -> Dict[str, Any]:
    return {
        "percent_total": 0.0,
        "percent_per_core": [],
        "freq_mhz": None,
        "freq_mhz_per_core": [],
        "count_logical": psutil.cpu_count(logical=True),
        "count_physical": psutil.cpu_count(logical=False),
        "loadavg": None,
    }


def get_cpu_block_psutil() -> Dict[str, Any]:
    block = get_cpu_base_block()
    freq = psutil.cpu_freq()
    block["percent_total"] = psutil.cpu_percent(interval=None)
    block["percent_per_core"] = psutil.cpu_percent(interval=None, percpu=True)
    block["freq_mhz"] = freq._asdict() if freq else None
    return block


def get_mem_block() -> Dict[str, Any]:
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
    return {
        "ram": {"total": vm.total, "used": vm.used, "available": vm.available, "percent": vm.percent},
        "swap": {"total": sm.total, "used": sm.used, "free": sm.free, "percent": sm.percent},
    }


def get_system_block() -> Dict[str, Any]:
    return {
        "uptime_sec": int(time.time() - psutil.boot_time()),
        "hostname": HOSTNAME,
        "pid": os.getpid(),
    }


# ===== Disk I/O =====
_prev_disk = psutil.disk_io_counters(perdisk=True)


def get_disk_io_block(elapsed: float) -> Dict[str, Any]:
    global _prev_disk
    curr = psutil.disk_io_counters(perdisk=True)
    result: Dict[str, Any] = {}

    for dev, io in curr.items():
        prev = _prev_disk.get(dev)
        if not prev:
            continue
        result[dev] = {
            "rate": {
                "read_bytes_per_s": round((io.read_bytes - prev.read_bytes) / elapsed, 3),
                "write_bytes_per_s": round((io.write_bytes - prev.write_bytes) / elapsed, 3),
                "read_iops": round((io.read_count - prev.read_count) / elapsed, 3),
                "write_iops": round((io.write_count - prev.write_count) / elapsed, 3),
            }
        }

    _prev_disk = curr
    return result


# ===== Network I/O =====
_prev_net = psutil.net_io_counters(pernic=True)


def get_net_io_block(elapsed: float) -> Dict[str, Any]:
    global _prev_net
    curr = psutil.net_io_counters(pernic=True)
    stats = psutil.net_if_stats()
    per_nic: Dict[str, Any] = {}
    total = {"rate": {"rx_bytes_per_s": 0.0, "tx_bytes_per_s": 0.0}, "cumulative": {"bytes_recv": 0, "bytes_sent": 0}}

    for nic, io in curr.items():
        prev = _prev_net.get(nic)
        if not prev:
            continue

        rx_bps = (io.bytes_recv - prev.bytes_recv) / elapsed
        tx_bps = (io.bytes_sent - prev.bytes_sent) / elapsed
        st = stats.get(nic)
        meta = {
            "isup": st.isup if st else None,
            "speed_mbps": st.speed if st and st.speed >= 0 else None,
            "mtu": st.mtu if st and st.mtu >= 0 else None,
            "duplex": st.duplex if st else None,
        }

        per_nic[nic] = {
            "rate": {"rx_bytes_per_s": round(rx_bps, 3), "tx_bytes_per_s": round(tx_bps, 3)},
            "cumulative": {"bytes_recv": io.bytes_recv, "bytes_sent": io.bytes_sent},
            "meta": meta,
        }

        total["rate"]["rx_bytes_per_s"] += rx_bps
        total["rate"]["tx_bytes_per_s"] += tx_bps
        total["cumulative"]["bytes_recv"] += io.bytes_recv
        total["cumulative"]["bytes_sent"] += io.bytes_sent

    _prev_net = curr
    total["rate"]["rx_bytes_per_s"] = round(total["rate"]["rx_bytes_per_s"], 3)
    total["rate"]["tx_bytes_per_s"] = round(total["rate"]["tx_bytes_per_s"], 3)
    return {"per_nic": per_nic, "total": total}


# ===== WMI / LibreHardwareMonitor =====
def get_lhm_wmi_data() -> List[Any]:
    if wmi is None:
        return []
    try:
        conn = wmi.WMI(namespace="root/LibreHardwareMonitor")
        return conn.Sensor()
    except Exception as e:
        return []


def _parse_core_index(name: str) -> Optional[int]:
    m = re.search(r"#(\d+)", name)
    if not m:
        return None
    idx = int(m.group(1)) - 1
    return idx if idx >= 0 else None


def _storage_key_from_parent(parent_path: str) -> str:
    parts = parent_path.strip("/").split("/")
    if len(parts) >= 2:
        return f"{parts[0]}{parts[1]}"
    return parent_path.strip("/") or "storage"


def _ensure_gpu_record(gpu_map: Dict[str, Dict[str, Any]], key: str) -> Dict[str, Any]:
    if key not in gpu_map:
        gpu_map[key] = {
            "usage_percent": 0.0,
            "temperature_celsius": None,
            "temperature_label": None,
            "_temps": [],
            "memory_used_mb": 0.0,
            "memory_total_mb": 0.0,
            "memory_percent": 0.0,
        }
    return gpu_map[key]


def process_lhm_sensors(sensors: List[Any], cpu_seed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cpu_block = dict(cpu_seed or get_cpu_base_block())
    cpu_loads: Dict[int, float] = {}
    cpu_clocks: Dict[int, float] = {}
    cpu_temps: List[Dict[str, Any]] = []
    storage_temps: Dict[str, List[Dict[str, Any]]] = {}
    gpu_map: Dict[str, Dict[str, Any]] = {}

    for sensor in sensors:
        sensor_type = str(getattr(sensor, "SensorType", ""))
        name = str(getattr(sensor, "Name", ""))
        value = getattr(sensor, "Value", None)
        parent_path = str(getattr(sensor, "Parent", ""))
        parent_lower = parent_path.lower()

        if value is None:
            continue

        # CPU sensors
        if "cpu" in parent_lower:
            if sensor_type == "Load":
                if name == "CPU Total":
                    cpu_block["percent_total"] = _safe_float(value)
                elif "CPU Core" in name:
                    idx = _parse_core_index(name)
                    if idx is not None:
                        cpu_loads[idx] = _safe_float(value)
            elif sensor_type == "Clock" and "CPU Core" in name:
                idx = _parse_core_index(name)
                if idx is not None:
                    cpu_clocks[idx] = _safe_float(value)
            elif sensor_type == "Temperature":
                cpu_temps.append({"label": name, "current": _safe_float(value)})
            continue

        # GPU sensors
        if "/gpu-" in parent_lower:
            gpu_key = parent_lower.strip("/")
            gpu = _ensure_gpu_record(gpu_map, gpu_key)
            lname = name.lower()

            if sensor_type == "Load":
                usage = _safe_float(value)
                if usage > gpu["usage_percent"]:
                    gpu["usage_percent"] = usage
            elif sensor_type == "Temperature":
                temp = round(_safe_float(value), 1)
                gpu["_temps"].append({"label": name, "current": temp})
                if gpu["temperature_celsius"] is None or temp > _safe_float(gpu["temperature_celsius"], -273.15):
                    gpu["temperature_celsius"] = temp
                    gpu["temperature_label"] = name
            elif sensor_type in {"SmallData", "Data", "Throughput"}:
                if "memory used" in lname:
                    gpu["memory_used_mb"] = _safe_float(value)
                elif "memory total" in lname:
                    gpu["memory_total_mb"] = _safe_float(value)
            continue

        # Storage temperature sensors
        if ("/hdd/" in parent_lower or "/nvme/" in parent_lower or "/ssd/" in parent_lower) and sensor_type == "Temperature":
            key = _storage_key_from_parent(parent_lower)
            storage_temps.setdefault(key, []).append(
                {"label": name if name != "Temperature" else f"{key} Temperature", "current": _safe_float(value)}
            )

    logical = cpu_block.get("count_logical") or len(cpu_loads)
    if logical and cpu_loads:
        cpu_block["percent_per_core"] = [cpu_loads.get(i, 0.0) for i in range(int(logical))]

    if cpu_clocks:
        max_idx = max(cpu_clocks.keys())
        cpu_block["freq_mhz_per_core"] = [cpu_clocks.get(i, 0.0) for i in range(max_idx + 1)]

    temps_block: Dict[str, Any] = {}
    if cpu_temps:
        temps_block["cpu"] = cpu_temps
    if storage_temps:
        temps_block["storage"] = storage_temps

    gpus: List[Dict[str, Any]] = []
    for key in sorted(gpu_map.keys()):
        gpu = gpu_map[key]
        mem_total = _safe_float(gpu.get("memory_total_mb"))
        mem_used = _safe_float(gpu.get("memory_used_mb"))
        gpu["memory_percent"] = round(mem_used / mem_total * 100.0, 1) if mem_total > 0 else 0.0
        gpu["usage_percent"] = round(_safe_float(gpu.get("usage_percent")), 1)

        temps = gpu.pop("_temps", [])
        gpu["temperatures"] = sorted(temps, key=lambda t: t.get("label", ""))
        gpus.append(gpu)

    return {
        "cpu": cpu_block,
        "temperatures": temps_block or None,
        "gpus": gpus,
    }


# ===== Payload builders (full/esp) =====
def _pick_cpu_temp_block(temps_block: Any) -> Dict[str, Any]:
    if not isinstance(temps_block, dict):
        return {}

    for key in ("k10temp", "coretemp", "cpu_thermal", "cpu"):
        entries = temps_block.get(key)
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and entry.get("current") is not None:
                    return {key: [{"current": _safe_float(entry.get("current"))}]}
    return {}


def _aggregate_disk_io(disk_block: Any) -> Dict[str, Any]:
    read_bps = 0.0
    write_bps = 0.0
    if isinstance(disk_block, dict):
        for disk in disk_block.values():
            if not isinstance(disk, dict):
                continue
            rate = disk.get("rate")
            if not isinstance(rate, dict):
                continue
            read_bps += _safe_float(rate.get("read_bytes_per_s"))
            write_bps += _safe_float(rate.get("write_bytes_per_s"))
    return {
        "total": {
            "rate": {
                "read_bytes_per_s": round(read_bps, 3),
                "write_bytes_per_s": round(write_bps, 3),
            }
        }
    }


def _normalize_gpu_payload(gpu_obj: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(gpu_obj, dict):
        return None
    temps = []
    raw_temps = gpu_obj.get("temperatures")
    if isinstance(raw_temps, list):
        for t in raw_temps:
            if not isinstance(t, dict):
                continue
            label = t.get("label")
            current = t.get("current")
            if label is None or current is None:
                continue
            temps.append({"label": str(label), "current": round(_safe_float(current), 1)})
            if len(temps) >= 3:
                break
    return {
        "usage_percent": round(_safe_float(gpu_obj.get("usage_percent")), 1),
        "temperature_celsius": round(_safe_float(gpu_obj.get("temperature_celsius"), default=0.0), 1)
        if gpu_obj.get("temperature_celsius") is not None
        else None,
        "memory_percent": round(_safe_float(gpu_obj.get("memory_percent")), 1),
        "temperatures": temps,
    }


def build_full_payload(now_ts: Optional[int] = None) -> Dict[str, Any]:
    gpus = metrics["gpu"] if isinstance(metrics["gpu"], list) else []
    return {
        "ts": int(time.time()) if now_ts is None else int(now_ts),
        "host": HOSTNAME,
        "system": metrics["system"],
        "cpu": metrics["cpu"],
        "memory": metrics["memory"],
        "disk_io": metrics["disk_io"],
        "temperatures": metrics["temperatures"],
        "network_io": metrics["network_io"],
        "gpu": gpus[0] if gpus else None,
        "gpus": gpus,
        "mqtt_stats": {
            "publish_ok": mqtt_stats["publish_ok"],
            "publish_err": mqtt_stats["publish_err"],
            "last_publish_rc": mqtt_stats["last_publish_rc"],
            "is_connected": mqtt_stats["is_connected"],
            "reconnects": mqtt_stats["reconnects"],
            "last_error": mqtt_stats["last_error"],
        },
    }


def build_esp_payload(now_ts: Optional[int] = None) -> Dict[str, Any]:
    cpu = metrics.get("cpu") if isinstance(metrics.get("cpu"), dict) else {}
    memory = metrics.get("memory") if isinstance(metrics.get("memory"), dict) else {}
    ram = memory.get("ram") if isinstance(memory.get("ram"), dict) else {}
    network = metrics.get("network_io") if isinstance(metrics.get("network_io"), dict) else {}
    net_total = network.get("total") if isinstance(network.get("total"), dict) else {}
    net_rate = net_total.get("rate") if isinstance(net_total.get("rate"), dict) else {}
    gpu_block = metrics.get("gpu")
    gpu_obj = gpu_block[0] if isinstance(gpu_block, list) and gpu_block else None

    payload = {
        "ts": int(time.time()) if now_ts is None else int(now_ts),
        "host": HOSTNAME,
        "cpu": {
            "percent_total": round(_safe_float(cpu.get("percent_total")), 1),
        },
        "memory": {
            "ram": {
                "percent": round(_safe_float(ram.get("percent")), 1),
                "used": int(_safe_float(ram.get("used"))),
                "total": int(_safe_float(ram.get("total"))),
            }
        },
        "disk_io": _aggregate_disk_io(metrics.get("disk_io")),
        "network_io": {
            "total": {
                "rate": {
                    "rx_bytes_per_s": round(_safe_float(net_rate.get("rx_bytes_per_s")), 3),
                    "tx_bytes_per_s": round(_safe_float(net_rate.get("tx_bytes_per_s")), 3),
                }
            }
        },
        "temperatures": _pick_cpu_temp_block(metrics.get("temperatures")),
        "gpu": _normalize_gpu_payload(gpu_obj),
    }
    return payload


def _build_esp_signature(payload: Dict[str, Any]) -> Dict[str, float]:
    cpu = payload.get("cpu", {})
    memory = payload.get("memory", {})
    ram = memory.get("ram", {}) if isinstance(memory, dict) else {}
    network = payload.get("network_io", {})
    net_total = network.get("total", {}) if isinstance(network, dict) else {}
    net_rate = net_total.get("rate", {}) if isinstance(net_total, dict) else {}
    disk = payload.get("disk_io", {})
    disk_total = disk.get("total", {}) if isinstance(disk, dict) else {}
    disk_rate = disk_total.get("rate", {}) if isinstance(disk_total, dict) else {}
    gpu = payload.get("gpu", {})
    temps = payload.get("temperatures", {})

    cpu_temp = 0.0
    if isinstance(temps, dict):
        for _, entries in temps.items():
            if isinstance(entries, list) and entries:
                first = entries[0]
                if isinstance(first, dict):
                    cpu_temp = _safe_float(first.get("current"))
                    break

    return {
        "cpu": _safe_float(cpu.get("percent_total")),
        "ram": _safe_float(ram.get("percent")),
        "cpu_temp": cpu_temp,
        "gpu": _safe_float(gpu.get("usage_percent")) if isinstance(gpu, dict) else 0.0,
        "gpu_temp": _safe_float(gpu.get("temperature_celsius")) if isinstance(gpu, dict) else 0.0,
        "net_rx": _safe_float(net_rate.get("rx_bytes_per_s")),
        "net_tx": _safe_float(net_rate.get("tx_bytes_per_s")),
        "disk_read": _safe_float(disk_rate.get("read_bytes_per_s")),
        "disk_write": _safe_float(disk_rate.get("write_bytes_per_s")),
    }


def reset_esp_publish_state():
    global _last_esp_signature, _last_esp_publish_monotonic
    _last_esp_signature = None
    _last_esp_publish_monotonic = 0.0


def should_publish_esp_payload(payload: Dict[str, Any], now_monotonic: Optional[float] = None) -> bool:
    global _last_esp_signature, _last_esp_publish_monotonic
    if now_monotonic is None:
        now_monotonic = time.monotonic()

    current = _build_esp_signature(payload)
    if _last_esp_signature is None:
        _last_esp_signature = current
        _last_esp_publish_monotonic = now_monotonic
        return True

    elapsed = now_monotonic - _last_esp_publish_monotonic
    if elapsed >= ESP_HEARTBEAT_INTERVAL_SEC:
        _last_esp_signature = current
        _last_esp_publish_monotonic = now_monotonic
        return True

    if elapsed < ESP_MIN_PUBLISH_INTERVAL_SEC:
        return False

    thresholds = {
        "cpu": ESP_CPU_DELTA,
        "ram": ESP_RAM_DELTA,
        "cpu_temp": ESP_TEMP_DELTA,
        "gpu": ESP_GPU_DELTA,
        "gpu_temp": ESP_TEMP_DELTA,
        "net_rx": ESP_NET_DELTA_BYTES,
        "net_tx": ESP_NET_DELTA_BYTES,
        "disk_read": ESP_DISK_DELTA_BYTES,
        "disk_write": ESP_DISK_DELTA_BYTES,
    }
    for key, threshold in thresholds.items():
        if abs(current.get(key, 0.0) - _last_esp_signature.get(key, 0.0)) >= threshold:
            _last_esp_signature = current
            _last_esp_publish_monotonic = now_monotonic
            return True
    return False


# ===== MQTT publish =====
def _publish_payload(payload: Dict[str, Any]):
    try:
        info = mqtt_client.publish(TOPIC, json.dumps(payload, separators=(",", ":")), qos=0, retain=False)
        mqtt_stats["last_publish_rc"] = info.rc
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            mqtt_stats["publish_ok"] += 1
        else:
            mqtt_stats["publish_err"] += 1
    except Exception as e:
        mqtt_stats["publish_err"] += 1
        mqtt_stats["last_error"] = str(e)


def publish_metrics() -> bool:
    if SENDER_PROFILE == "esp":
        payload = build_esp_payload()
        if not should_publish_esp_payload(payload):
            return False
        _publish_payload(payload)
        return True

    payload = build_full_payload()
    _publish_payload(payload)
    return True


# ===== Async tasks =====
async def loop_cpu_mem():
    while True:
        metrics["cpu"] = get_cpu_block_psutil()
        metrics["memory"] = get_mem_block()
        metrics["system"] = get_system_block()
        await asyncio.sleep(1)


async def loop_disk():
    last = time.time()
    while True:
        now = time.time()
        metrics["disk_io"] = get_disk_io_block(max(1e-6, now - last))
        last = now
        await asyncio.sleep(3)


async def loop_network():
    last = time.time()
    while True:
        now = time.time()
        metrics["network_io"] = get_net_io_block(max(1e-6, now - last))
        last = now
        await asyncio.sleep(1)


async def loop_lhm_wmi():
    while True:
        sensors = get_lhm_wmi_data()
        if sensors:
            out = process_lhm_sensors(sensors, metrics.get("cpu") if isinstance(metrics.get("cpu"), dict) else None)
            metrics["cpu"] = out["cpu"]
            metrics["temperatures"] = out["temperatures"]
            metrics["gpu"] = out["gpus"]
        await asyncio.sleep(10)


async def loop_publish():
    while True:
        publish_metrics()
        await asyncio.sleep(PUBLISH_INTERVAL_SEC)


async def mqtt_reconnector():
    retry_delay = 3
    max_delay = 60

    while True:
        if not mqtt_client.is_connected():
            mqtt_stats["reconnects"] += 1
            try:
                mqtt_client.reconnect()
                await asyncio.sleep(2)
                if mqtt_client.is_connected():
                    retry_delay = 3
                else:
                    retry_delay = min(retry_delay * 2, max_delay)
            except Exception as e:
                mqtt_stats["last_error"] = str(e)
                retry_delay = min(retry_delay * 2, max_delay)
        else:
            retry_delay = 3

        await asyncio.sleep(retry_delay)


# ===== MAIN =====
async def main():
    if platform.system() != "Windows":
        print("This script is only for Windows.")
        return

    if not BROKER_HOST:
        print("MQTT Error: BROKER_HOST is not set in environment variables.")
        return

    print(f"Async Agent for Windows started on {HOSTNAME}")
    print(f"Sender profile: {SENDER_PROFILE}")

    if wmi is None:
        print("python wmi package is not installed. LHM/WMI metrics will be unavailable.")
    else:
        _lhm_manager.ensure_ready()

    if SENDER_PROFILE == "esp":
        reset_esp_publish_state()

    psutil.cpu_percent(interval=None, percpu=True)

    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=60)
    mqtt_client.connect_async(BROKER_HOST, BROKER_PORT)
    mqtt_client.loop_start()

    try:
        await asyncio.gather(
            loop_cpu_mem(),
            loop_disk(),
            loop_network(),
            loop_lhm_wmi(),
            loop_publish(),
            mqtt_reconnector(),
        )
    finally:
        mqtt_client.loop_stop()
        try:
            mqtt_client.disconnect()
        except Exception:
            pass
        _lhm_manager.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped by user.")

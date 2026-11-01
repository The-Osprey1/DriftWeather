#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Hardware & System Health Telemetry
Collects CPU temperature, memory, disk usage, uptime, and operational metrics.
"""

import os
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any

from config.settings import get_settings
from .wifi_watchdog import get_wifi_watchdog

logger = logging.getLogger("G4Cast.Health")

def get_cpu_temp() -> float:
    """Read CPU temperature in Celsius."""
    if os.name == "nt":
        return 42.0

    # 1. Try Linux thermal zone
    tz_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if tz_path.exists():
        try:
            with open(tz_path, "r") as f:
                return round(float(f.read().strip()) / 1000.0, 1)
        except Exception:
            pass

    # 2. Try vcgencmd (Raspberry Pi specific)
    try:
        res = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True, timeout=2)
        # Output: temp=48.2'C
        val = res.stdout.strip().replace("temp=", "").replace("'C", "")
        return float(val)
    except Exception:
        pass

    return 0.0

def get_uptime_seconds() -> float:
    """Read system uptime in seconds."""
    if os.name == "nt":
        return 3600.0 * 12.5

    uptime_path = Path("/proc/uptime")
    if uptime_path.exists():
        try:
            with open(uptime_path, "r") as f:
                return float(f.read().split()[0])
        except Exception:
            pass
    return 0.0

def format_uptime(uptime_sec: float) -> str:
    days = int(uptime_sec // 86400)
    hours = int((uptime_sec % 86400) // 3600)
    minutes = int((uptime_sec % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"

def get_memory_stats() -> Dict[str, Any]:
    """Read memory usage stats."""
    if os.name == "nt":
        return {"total_mb": 512, "used_mb": 140, "free_mb": 372, "percent": 27.3}

    mem_path = Path("/proc/meminfo")
    if mem_path.exists():
        try:
            mem = {}
            with open(mem_path, "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        mem[k] = int(v)
            total = mem.get("MemTotal", 1)
            avail = mem.get("MemAvailable", mem.get("MemFree", 0))
            used = total - avail
            return {
                "total_mb": round(total / 1024),
                "used_mb": round(used / 1024),
                "free_mb": round(avail / 1024),
                "percent": round((used / total) * 100, 1)
            }
        except Exception as e:
            logger.debug(f"Memory parse error: {e}")

    return {"total_mb": 0, "used_mb": 0, "free_mb": 0, "percent": 0.0}

def get_disk_stats() -> Dict[str, Any]:
    """Read disk usage stats."""
    try:
        usage = shutil.disk_usage("/")
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent": round((usage.used / usage.total) * 100, 1)
        }
    except Exception:
        return {"total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0, "percent": 0.0}

class SystemHealth:
    def __init__(self):
        self.settings = get_settings()
        self.watchdog = get_wifi_watchdog()

    def get_full_diagnostics(self, weather_updater=None, display=None) -> Dict[str, Any]:
        """Compile complete system diagnostics dictionary."""
        uptime_sec = get_uptime_seconds()
        cpu_temp_c = get_cpu_temp()
        cpu_temp_f = round(cpu_temp_c * 9.0 / 5.0 + 32, 1) if cpu_temp_c > 0 else 0.0

        net_info = self.watchdog.get_network_info()

        last_sync_ts = weather_updater.last_sync_timestamp if weather_updater else 0.0
        last_sync_str = time.strftime("%I:%M:%S %p", time.localtime(last_sync_ts)) if last_sync_ts > 0 else "Never"
        last_sync_ago = round(time.time() - last_sync_ts) if last_sync_ts > 0 else 999999

        refresh_count = display.refresh_count if display else 0

        return {
            "system": {
                "version": self.settings.get("version", default="2.1.0"),
                "uptime": format_uptime(uptime_sec),
                "uptime_seconds": round(uptime_sec),
                "cpu_temp_c": cpu_temp_c,
                "cpu_temp_f": cpu_temp_f,
                "memory": get_memory_stats(),
                "disk": get_disk_stats()
            },
            "network": {
                "is_online": net_info["is_connected"],
                "ssid": net_info["ssid"],
                "ip_address": net_info["ip_address"],
                "signal_percent": net_info["signal_percent"],
                "signal_dbm": net_info["signal_dbm"]
            },
            "weather": {
                "city": self.settings.get("weather", "city", default="Eastvale, US"),
                "last_sync_time": last_sync_str,
                "last_sync_ago_seconds": last_sync_ago,
                "api_status": "Operational" if (weather_updater and weather_updater.last_update_success) else "Cached / Pending",
                "kcno_enabled": self.settings.get("weather", "use_kcno", default=True)
            },
            "display": {
                "refresh_count": refresh_count,
                "mode": "Waveshare 7.5\" V2 (800x480)"
            }
        }

_health_instance = None

def get_health():
    global _health_instance
    if _health_instance is None:
        _health_instance = SystemHealth()
    return _health_instance

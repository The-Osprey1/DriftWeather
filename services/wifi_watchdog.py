#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Wi-Fi Watchdog & Self-Healing Network Service
Monitors network connectivity with safe checks (HTTP/ICMP), executes non-disruptive
auto-recovery only during confirmed persistent outages, and triggers immediate weather sync upon connection restoration.
"""

import os
import time
import socket
import logging
import urllib.request
import subprocess
import threading
from typing import Callable, Optional
from pathlib import Path

logger = logging.getLogger("G4Cast.Watchdog")

class WifiWatchdog:
    _instance = None
    _lock = threading.RLock()

    def __init__(self, check_interval: int = 30, ping_host: str = "1.1.1.1", max_retries: int = 5):
        self.check_interval = max(15, check_interval)
        self.ping_host = ping_host
        self.max_retries = max_retries

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_recovered_callbacks = []

        self.is_connected = True
        self.last_online_time = time.time()
        self.consecutive_failures = 0
        self.last_check_time = 0

    @classmethod
    def get_instance(cls, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(**kwargs)
            return cls._instance

    def register_recovery_callback(self, callback: Callable[[], None]):
        """Register a callback function to execute immediately when connectivity returns."""
        with self._lock:
            if callback not in self._on_recovered_callbacks:
                self._on_recovered_callbacks.append(callback)

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, name="WifiWatchdogThread", daemon=True)
            self._thread.start()
            logger.info("Wi-Fi watchdog started (check interval: %ds)", self.check_interval)

    def stop(self):
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def check_connectivity(self) -> bool:
        """
        Reliable multi-tier connectivity check:
        1. Quick HTTP HEAD/GET to reliable endpoint (Google 204 or Cloudflare) with 3s timeout
        2. System ICMP ping fallback
        3. Local Wi-Fi association check via iwgetid
        """
        self.last_check_time = time.time()

        # Method 1: Lightweight HTTP probe (doesn't get blocked like raw TCP port 53)
        for probe_url in ("http://clients3.google.com/generate_204", "http://1.1.1.1"):
            try:
                req = urllib.request.Request(probe_url, headers={"User-Agent": "G4Cast/2.1"})
                with urllib.request.urlopen(req, timeout=3.5) as response:
                    if response.status in (200, 204):
                        return True
            except Exception:
                continue

        # Method 2: Standard ICMP ping
        try:
            cmd = ["ping", "-c", "1", "-W", "2", "8.8.8.8"] if os.name != "nt" else ["ping", "-n", "1", "-w", "2000", "8.8.8.8"]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            if res.returncode == 0:
                return True
        except Exception:
            pass

        # Method 3: Check if Wi-Fi interface is still associated to an SSID
        if os.name != "nt":
            try:
                res = subprocess.run(["/sbin/iwgetid", "-r"], capture_output=True, text=True, timeout=2)
                ssid = res.stdout.strip()
                if ssid:
                    # Wi-Fi link is up, maybe just transient WAN latency; consider connected
                    return True
            except Exception:
                pass

        return False

    def attempt_recovery(self):
        """
        Safe, non-disruptive progressive recovery.
        Never tears down active Wi-Fi connections aggressively on transient packet loss.
        """
        if os.name == "nt":
            logger.info("Watchdog: Simulated recovery on Windows")
            return

        # Only intervene if we have had multiple CONFIRMED consecutive failures (at least 90 seconds of outage)
        if self.consecutive_failures < 3:
            logger.info("Watchdog: Failure #%d (waiting for confirmation before recovery action)", self.consecutive_failures)
            return

        logger.warning("Watchdog: Persistent network outage confirmed (%d failures). Re-initiating connection...", self.consecutive_failures)

        # Step 1: Ensure radio is on
        try:
            subprocess.run(["/usr/bin/nmcli", "radio", "wifi", "on"], timeout=5, check=False)
        except Exception:
            pass

        # Step 2: Use G4Cast's dedicated ConnectWifi.py helper if available
        base_dir = Path(__file__).resolve().parent.parent
        connect_script = base_dir / "ConnectWifi.py"
        if connect_script.exists():
            try:
                logger.info("Executing ConnectWifi.py helper...")
                subprocess.run(["/usr/bin/python3", str(connect_script)], timeout=25, check=False)
                time.sleep(4)
                if self.check_connectivity():
                    logger.info("ConnectWifi.py successfully restored network link.")
                    return
            except Exception as e:
                logger.error("ConnectWifi error: %s", e)

        # Step 3: Extreme fallback - only restart NetworkManager if completely dead for > 8 checks (~4 minutes)
        if self.consecutive_failures >= 8:
            logger.warning("Watchdog: Extreme outage (>4 min). Restarting NetworkManager service...")
            try:
                subprocess.run(["sudo", "systemctl", "restart", "NetworkManager"], timeout=15, check=False)
                time.sleep(6)
            except Exception as e:
                logger.error("NetworkManager restart error: %s", e)

    def _run_loop(self):
        while self._running:
            ok = self.check_connectivity()
            was_offline = not self.is_connected

            if ok:
                self.is_connected = True
                self.last_online_time = time.time()
                self.consecutive_failures = 0

                if was_offline:
                    logger.info("=== Wi-Fi Connectivity Restored! Triggering instant weather sync ===")
                    self._notify_recovered()
            else:
                self.consecutive_failures += 1
                self.is_connected = False
                self.attempt_recovery()

            # Sleep in small increments for responsive stop()
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _notify_recovered(self):
        with self._lock:
            callbacks = list(self._on_recovered_callbacks)
        for cb in callbacks:
            try:
                cb()
            except Exception as e:
                logger.error("Error in recovery callback: %s", e)

    def get_network_info(self) -> dict:
        """Get live Wi-Fi telemetry for web portal and diagnostics."""
        info = {
            "is_connected": self.is_connected,
            "consecutive_failures": self.consecutive_failures,
            "last_online_ago_seconds": round(time.time() - self.last_online_time),
            "ssid": "Unknown",
            "ip_address": "127.0.0.1",
            "signal_dbm": None,
            "signal_percent": 0
        }

        if os.name == "nt":
            info["ssid"] = "Windows-Dev-Net"
            info["ip_address"] = "192.168.1.100"
            info["signal_percent"] = 90
            return info

        try:
            res_ip = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=2)
            ips = res_ip.stdout.strip().split()
            if ips:
                info["ip_address"] = ips[0]

            res_ssid = subprocess.run(["/sbin/iwgetid", "-r"], capture_output=True, text=True, timeout=2)
            if res_ssid.stdout.strip():
                info["ssid"] = res_ssid.stdout.strip()

            res_nm = subprocess.run(
                ["/usr/bin/nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "device", "wifi"],
                capture_output=True, text=True, timeout=3
            )
            for line in res_nm.stdout.strip().splitlines():
                if line.startswith("yes:"):
                    parts = line.split(":")
                    if len(parts) >= 3:
                        info["ssid"] = parts[1]
                        info["signal_percent"] = int(parts[2])
                        info["signal_dbm"] = (info["signal_percent"] // 2) - 100
                    break
        except Exception as e:
            logger.debug("Network telemetry error: %s", e)

        return info

def get_wifi_watchdog(**kwargs):
    return WifiWatchdog.get_instance(**kwargs)

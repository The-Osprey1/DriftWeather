#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Theme & Dark Mode Switcher Utility
Controls visual appearance (Light, Dark, and Solar Auto-Switching) and ensures
persistent synchronization across OverlayFS microSD partitions.

Usage:
  python3 switch_theme.py off       # Force Light Mode (white background)
  python3 switch_theme.py on        # Force Dark Mode (black background)
  python3 switch_theme.py auto      # Solar Auto-Switching (sunrise/sunset)
  python3 switch_theme.py status    # Show current visual and astronomical state
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime, timezone, timedelta

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.settings import get_settings, normalize_dark_mode
from services.scheduler import evaluate_dark_mode, calculate_astronomical_solar

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("G4Cast.SwitchTheme")

def print_help():
    print("G4Cast Theme & Dark Mode Switcher")
    print("---------------------------------")
    print("Available Commands:")
    print("  off     - Force Light Mode (white canvas, black typography)")
    print("  on      - Force Dark Mode (deep black canvas, white typography)")
    print("  auto    - Solar Auto-Switching (automatically switches at sunset/sunrise)")
    print("  status  - Display active theme, solar schedule, and partition status")
    print("\nUsage:")
    print("  python3 switch_theme.py <off|on|auto|status>")
    print("Example: python3 switch_theme.py auto")

def trigger_refresh():
    """Trigger an immediate display refresh via web service or systemctl."""
    # Attempt local web API refresh first
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:8080/api/refresh", data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                print("[+] E-paper refresh signal delivered to running web server.")
                return
    except Exception:
        pass

    # Fallback to systemctl restart if G4Cast.service is active
    try:
        res = subprocess.run(["systemctl", "is-active", "G4Cast.service"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip() == "active":
            print("[*] Restarting G4Cast.service to apply new theme...")
            subprocess.run(["sudo", "systemctl", "restart", "G4Cast.service"], check=False)
            print("[+] Screen refresh triggered successfully!")
            return
    except Exception:
        pass

    # Standalone execution fallback
    try:
        from services.scheduler import get_scheduler
        scheduler = get_scheduler()
        scheduler.update_display_now(force_full=False)
        print("[+] Screen rendered and updated in memory/display.")
    except Exception as e:
        print(f"[*] Note: Could not trigger immediate display update ({e}). Setting will take effect on next cycle.")

def show_status():
    settings = get_settings()
    mode = settings.get("display", "dark_mode", default="off")

    cache_file = os.path.join(BASE_DIR, "weather_cache.json")
    weather_data = None
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                c = json.load(f)
                weather_data = c.get("current")
        except Exception:
            pass

    lat = 33.963
    lon = -117.564
    if weather_data and "coord" in weather_data:
        lat = weather_data["coord"].get("lat", lat)
        lon = weather_data["coord"].get("lon", lon)

    is_dark = evaluate_dark_mode(mode, weather_data=weather_data, lat=lat, lon=lon)
    overlay_mounted = os.path.exists("/media/root-ro")

    print("\n=======================================================")
    print("        G4Cast Theme & Dark Mode Status Report        ")
    print("=======================================================")
    print(f"  Configured Mode      : {mode.upper()}")
    print(f"  Active Canvas State  : {'DARK MODE (Black)' if is_dark else 'LIGHT MODE (White)'}")
    print(f"  OverlayFS Partition  : {'Mounted (/media/root-ro)' if overlay_mounted else 'Not Active (Dev / Read-Write)'}")
    print(f"  Reference Coords     : Lat {lat:.4f}, Lon {lon:.4f}")

    if weather_data and "sys" in weather_data:
        sr_ts = weather_data["sys"].get("sunrise", 0)
        ss_ts = weather_data["sys"].get("sunset", 0)
        tz_offset = weather_data.get("timezone", -25200)
        if sr_ts and ss_ts:
            sr_dt = datetime.fromtimestamp(sr_ts, timezone.utc) + timedelta(seconds=tz_offset)
            ss_dt = datetime.fromtimestamp(ss_ts, timezone.utc) + timedelta(seconds=tz_offset)
            print(f"  Solar Schedule (Cache): Sunrise {sr_dt.strftime('%I:%M %p')}, Sunset {ss_dt.strftime('%I:%M %p')}")
    else:
        sr_s, ss_s = calculate_astronomical_solar(lat, lon)
        if sr_s is not None and ss_s is not None:
            sr_h, sr_m = int(sr_s // 60), int(sr_s % 60)
            ss_h, ss_m = int(ss_s // 60), int(ss_s % 60)
            print(f"  Solar Schedule (Astro): Sunrise {sr_h:02d}:{sr_m:02d} Solar, Sunset {ss_h:02d}:{ss_m:02d} Solar")
    print("=======================================================\n")

def switch(target_mode):
    key = target_mode.lower().strip()
    if key in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    if key == "status":
        show_status()
        sys.exit(0)

    # Legacy numeric theme backwards-compatibility
    legacy_map = {"1": "off", "2": "on", "3": "off", "4": "off"}
    if key in legacy_map:
        print(f"[*] Mapping legacy theme option '{key}' to Dark Mode '{legacy_map[key]}'...")
        key = legacy_map[key]

    normalized = normalize_dark_mode(key)
    if key not in ("off", "on", "auto", "light", "dark", "solar") and normalized == "off" and key != "off":
        print(f"Error: Unknown command or theme '{target_mode}'.")
        print_help()
        sys.exit(1)

    settings = get_settings()
    settings.set("display", "dark_mode", normalized)

    print(f"[*] Setting display.dark_mode to '{normalized}'...")
    saved = settings.save(persist=False)
    if not saved:
        print("[!] Error saving settings.json")
        sys.exit(1)

    # Synchronous OverlayFS persistence to prevent process exit before microSD write
    if os.path.exists("/media/root-ro"):
        print("[*] Detected OverlayFS. Synchronously persisting to microSD card...")
        persisted = settings._persist_to_overlayfs()
        if persisted:
            print("[+] Successfully persisted settings to /media/root-ro.")
        else:
            print("[!] Warning: Could not remount /media/root-ro (may need sudo).")

    print(f"[+] Successfully configured Dark Mode to: {normalized.upper()}")
    trigger_refresh()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)
    switch(sys.argv[1])

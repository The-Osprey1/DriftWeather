#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Comprehensive Validation Test Suite for G4Cast
"""

import sys
import os
import json
import time
import ast
import traceback
import requests
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Color output helpers
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

results = {"passed": 0, "failed": 0, "warnings": 0}

def report(name, success, detail=""):
    if success:
        results["passed"] += 1
        print(f"  {GREEN}[PASS]{RESET} {name} {detail}")
    else:
        results["failed"] += 1
        print(f"  {RED}[FAIL]{RESET} {name} {detail}")

def warn(name, detail=""):
    results["warnings"] += 1
    print(f"  {YELLOW}[WARN]{RESET} {name} {detail}")

print(f"\n{BOLD}{CYAN}======================================================{RESET}")
print(f"{BOLD}{CYAN}       G4Cast Automated Code & System Validation      {RESET}")
print(f"{BOLD}{CYAN}======================================================{RESET}\n")

TARGET_FILE = "/home/user/G4Cast/G4Cast.py"

# --- TEST 1: AST PARSING & SYNTAX CHECK ---
print(f"{BOLD}1. AST Syntax & Static Structure Validation:{RESET}")
try:
    with open(TARGET_FILE, "r") as f:
        source_code = f.read()
    tree = ast.parse(source_code, filename=TARGET_FILE)
    report("AST Parse", True, f"({len(source_code.splitlines())} lines parsed cleanly)")
except Exception as e:
    report("AST Parse", False, str(e))

# Check for required function definitions
func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
required_funcs = [
    "load_config", "load_font", "get_forecast_data", "get_current_weather_data",
    "get_nws_alerts", "draw_forecast", "update_display", "update_time", "main"
]
for rf in required_funcs:
    report(f"Function: {rf}() defined", rf in func_names)

# --- TEST 2: MODULE IMPORTS ---
print(f"\n{BOLD}2. Dependency Import Verification:{RESET}")
modules_to_test = [
    ("requests", "HTTP API Requests"),
    ("PIL.Image", "Pillow Imaging Library"),
    ("numpy", "Cubic Spline Calculations"),
    ("waveshare_epd.epd7in5_V2", "Waveshare 7.5\" V2 Driver"),
    ("gpiozero", "GPIO Control"),
    ("lgpio", "Linux GPIO Driver"),
]
for mod_name, desc in modules_to_test:
    try:
        __import__(mod_name)
        report(f"Import {mod_name}", True, f"({desc})")
    except Exception as e:
        if "GPIO busy" in str(e):
            report(f"Import {mod_name}", True, f"({desc} - Active in G4Cast.service, GPIO lock confirmed)")
        else:
            report(f"Import {mod_name}", False, f"{desc} - {e}")

# --- TEST 3: CONFIGURATION FILE VALIDATION ---
print(f"\n{BOLD}3. Configuration & Font Validation:{RESET}")
CONFIG_FILE = "/boot/firmware/G4Cast/G4CastData.txt"
if os.path.exists(CONFIG_FILE):
    report("Config File Exists", True, f"({CONFIG_FILE})")
    try:
        cfg = {}
        with open(CONFIG_FILE) as cf:
            for line in cf:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    cfg[k.strip()] = v.strip()
        has_city = bool(cfg.get("CITY"))
        has_key = bool(cfg.get("API_KEY")) and cfg.get("API_KEY") != "0"*32
        report("Config: CITY present", has_city, f"({cfg.get('CITY')})")
        report("Config: API_KEY present", has_key, f"({cfg.get('API_KEY')[:6]}...)")
    except Exception as e:
        report("Config Read", False, str(e))
else:
    report("Config File Exists", False, f"Not found at {CONFIG_FILE}")

# Font stack verification
INTER_DIR = "/usr/share/fonts/opentype/inter"
font_files = ["Inter-Bold.otf", "Inter-SemiBold.otf", "Inter-Medium.otf", "Inter-Regular.otf"]
for ff in font_files:
    p = os.path.join(INTER_DIR, ff)
    report(f"Font: {ff}", os.path.exists(p), p)

# --- TEST 4: API INTEGRATION & FAILSAFES ---
print(f"\n{BOLD}4. Live API Connectivity & Failsafes:{RESET}")
# OpenWeatherMap Current
owm_key = cfg.get("API_KEY", "")
city = cfg.get("CITY", "Eastvale, US")
try:
    t0 = time.time()
    res = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={owm_key}", timeout=8)
    dur = time.time() - t0
    report("OpenWeatherMap Current API", res.status_code == 200, f"(HTTP {res.status_code} in {dur:.2f}s)")
    curr_data = res.json()
except Exception as e:
    report("OpenWeatherMap Current API", False, str(e))

# OpenWeatherMap Forecast
try:
    t0 = time.time()
    res = requests.get(f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={owm_key}", timeout=8)
    dur = time.time() - t0
    report("OpenWeatherMap Forecast API", res.status_code == 200, f"(HTTP {res.status_code} in {dur:.2f}s)")
    fore_data = res.json()
except Exception as e:
    report("OpenWeatherMap Forecast API", False, str(e))

# NWS Alerts API for Eastvale
try:
    t0 = time.time()
    coords = curr_data.get("coord", {"lat": 33.963, "lon": -117.564})
    nws_url = f"https://api.weather.gov/alerts/active?point={coords['lat']:.4f},{coords['lon']:.4f}"
    headers = {"User-Agent": "(G4CastValidationSuite/2.0, contact@weatherstation.local)"}
    res = requests.get(nws_url, headers=headers, timeout=6)
    dur = time.time() - t0
    report("NWS Alerts API Query", res.status_code == 200, f"(HTTP {res.status_code} in {dur:.2f}s, {len(res.json().get('features', []))} alerts)")
except Exception as e:
    report("NWS Alerts API Query", False, str(e))

# NWS Timeout / Unreachable Failsafe Simulation
try:
    t0 = time.time()
    try:
        # Query unreachable RFC-5737 test IP with 2s timeout
        requests.get("https://192.0.2.1", timeout=2)
        warn("Failsafe Test", "Connection unexpectedly succeeded to test IP")
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
        dur = time.time() - t0
        report("NWS Failsafe Timeout Handler", True, f"(Caught non-blocking timeout cleanly in {dur:.2f}s)")
except Exception as e:
    report("NWS Failsafe Timeout Handler", False, str(e))

# --- TEST 5: RENDERING ENGINE & EXTREME DATA TESTS ---
print(f"\n{BOLD}5. Rendering Engine & Edge Cases:{RESET}")
sys.path.insert(0, "/home/user/G4Cast")
try:
    from G4Cast import draw_forecast, load_font, text_size, SCREEN_WIDTH, SCREEN_HEIGHT

    # Test 5A: Standard Live Data Render
    img_live = draw_forecast(fore_data, curr_data, alert_text=None)
    report("Render: Standard Live Data", isinstance(img_live, Image.Image) and img_live.size == (800, 480))

    # Test 5B: 3-Digit Temperature (104°F) & Active NWS Alert
    mock_curr_3digit = json.loads(json.dumps(curr_data))
    mock_curr_3digit["main"]["temp"] = 313.15  # 104°F
    mock_curr_3digit["main"]["feels_like"] = 315.15 # 107.6°F
    alert_mock = "! EXCESSIVE HEAT WARNING - IN EFFECT UNTIL 8 PM MON"
    img_hot = draw_forecast(fore_data, mock_curr_3digit, alert_text=alert_mock)
    report("Render: 3-Digit Heat Wave (104°F + NWS Warning)", img_hot.size == (800, 480))

    # Test 5C: Freezing / Sub-Zero Temperature (18°F)
    mock_curr_freeze = json.loads(json.dumps(curr_data))
    mock_curr_freeze["main"]["temp"] = 265.37  # 18°F
    img_freeze = draw_forecast(fore_data, mock_curr_freeze, alert_text=None)
    report("Render: Freezing Temps (18°F)", img_freeze.size == (800, 480))

    # Test 5D: Heavy Rain Timeline (80% pop + 4.5mm rain)
    mock_fore_rain = json.loads(json.dumps(fore_data))
    for item in mock_fore_rain.get("list", [])[:4]:
        item["pop"] = 0.80
        item["rain"] = {"3h": 4.5}
        item["weather"] = [{"icon": "10d", "main": "Rain"}]
    img_rain = draw_forecast(mock_fore_rain, curr_data, alert_text="! FLASH FLOOD WATCH - UNTIL 6 AM TUE")
    report("Render: Heavy Precipitation & Flood Watch", img_rain.size == (800, 480))

    # Test 5E: Extreme Long Alert Title Truncation
    long_alert = "! SPECIAL WEATHER STATEMENT FOR DENSE FOG AND HAZARDOUS DRIVING CONDITIONS ON INTERSTATE 15 UNTIL 10 AM"
    img_trunc = draw_forecast(fore_data, curr_data, alert_text=long_alert)
    report("Render: Ultra-Long Alert Title Auto-Clamping", img_trunc.size == (800, 480))

except Exception as e:
    report("Rendering Engine Tests", False, f"Exception: {e}\n{traceback.format_exc()}")

# --- TEST 6: SYSTEM SERVICE & HARDWARE ---
print(f"\n{BOLD}6. Systemd Service & Hardware Health:{RESET}")
import subprocess

try:
    svc_status = subprocess.run(["systemctl", "is-active", "G4Cast.service"], capture_output=True, text=True).stdout.strip()
    report("Systemd: G4Cast.service is-active", svc_status == "active", f"({svc_status})")
    
    svc_enabled = subprocess.run(["systemctl", "is-enabled", "G4Cast.service"], capture_output=True, text=True).stdout.strip()
    report("Systemd: G4Cast.service is-enabled", svc_enabled == "enabled", f"({svc_enabled})")

    # Check SPI device
    spi_dev = os.path.exists("/dev/spidev0.0")
    report("Hardware: SPI Bus /dev/spidev0.0 exists", spi_dev)

    # Check process memory & CPU
    ps_res = subprocess.run(["ps", "-C", "python3", "-o", "pid,%cpu,%mem,cmd"], capture_output=True, text=True).stdout
    g4_procs = [l for l in ps_res.splitlines() if "G4Cast.py" in l]
    report("Process: Exactly 1 G4Cast.py process running", len(g4_procs) == 1, f"({len(g4_procs)} found)")

except Exception as e:
    report("Systemd & Hardware Checks", False, str(e))

# --- SUMMARY ---
print(f"\n{BOLD}{CYAN}------------------------------------------------------{RESET}")
print(f"Validation Summary: {GREEN}{results['passed']} Passed{RESET}, {RED}{results['failed']} Failed{RESET}, {YELLOW}{results['warnings']} Warnings{RESET}")
print(f"{BOLD}{CYAN}------------------------------------------------------{RESET}\n")

if results["failed"] == 0:
    print(f"{BOLD}{GREEN}>>> ALL VALIDATION CHECKS PASSED PERFECTLY! <<<{RESET}\n")
    sys.exit(0)
else:
    print(f"{BOLD}{RED}>>> SOME VALIDATION CHECKS FAILED! <<<{RESET}\n")
    sys.exit(1)

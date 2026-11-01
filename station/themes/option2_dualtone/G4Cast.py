#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Clean, Decluttered G4Cast Weather Display Controller
Features:
- Dynamic auto-scaling for 3-digit temperatures (100°F+)
- Smart dynamic precipitation timeline (precipitation bars & rain chance % appear only when rain is forecast)
- Perfectly centered card elements and 5-day forecast
- Low-power minute clock refresh with anti-burn-in offset
"""

import os
import sys
import logging
import requests
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont
import time
import numpy as np
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- WAVESHARE E-PAPER IMPORT ---
try:
    from waveshare_epd import epd7in5_V2
    logging.info("Waveshare e-ink library imported")
except Exception as e:
    epd7in5_V2 = None
    logging.error(f"Waveshare e-ink library not found: {e}")

epd = None

# --- PATHS ---
base_dir = Path(__file__).resolve().parent
picdir = f"{base_dir}/pic"
CONFIG_FILE = "/boot/firmware/G4Cast/G4CastData.txt"

# --- SCREEN SETTINGS ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
ROTATE_DEGREES = 180
SHOW_BOOT_SCREEN = True

# --- STATUS LOG ---
status_log = []
line_msg = 0

# --- FONT DEFINITIONS ---
FONT_DIR = "/usr/share/fonts/opentype/inter"
FONTS = {
    "bold": f"{FONT_DIR}/Inter-Bold.otf",
    "semibold": f"{FONT_DIR}/Inter-SemiBold.otf",
    "medium": f"{FONT_DIR}/Inter-Medium.otf",
    "regular": f"{FONT_DIR}/Inter-Regular.otf",
    "fallback": f"{picdir}/Font.ttc",
    "dejavu": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
}

DEG = "\u00b0"

def load_font(size, weight="bold"):
    target_path = FONTS.get(weight, FONTS["bold"])
    candidates = [
        target_path,
        FONTS["bold"],
        FONTS["semibold"],
        FONTS["medium"],
        FONTS["dejavu"],
        FONTS["fallback"]
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

def text_size(draw, text, font):
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), str(text), font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    return draw.textsize(str(text), font=font)

def draw_centered_text(draw, cx, y, text, font, fill):
    w, h = text_size(draw, text, font)
    draw.text((cx - w // 2, y), text, font=font, fill=fill)
    return w, h

def draw_droplet(draw, cx, cy, size=10, fill=0):
    r = size // 2
    draw.ellipse([cx - r, cy - r // 2, cx + r, cy + r + r // 2], fill=fill)
    draw.polygon([(cx - r + 1, cy), (cx, cy - size), (cx + r - 1, cy)], fill=fill)

# --- CONFIG & COLORS ---
CITY = ""
API_KEY = ""
USE_METRIC = False
DISPLAY_TEXT = ""
DARK_MODE = False
USE_24HFORMAT = False
USE_AVGTEMP = False
DEMO_MODE = False

COLOR_BG = 255
COLOR_FG = 0
COLOR_LINE = 90
COLOR_GRID = 190
COLOR_BAR = 160

def update_colors():
    global COLOR_BG, COLOR_FG, COLOR_LINE, COLOR_GRID, COLOR_BAR
    if DARK_MODE:
        COLOR_BG = 0
        COLOR_FG = 255
        COLOR_LINE = 180
        COLOR_GRID = 110
        COLOR_BAR = 200
    else:
        COLOR_BG = 255
        COLOR_FG = 0
        COLOR_LINE = 90
        COLOR_GRID = 190
        COLOR_BAR = 160

def load_config(path=CONFIG_FILE):
    config = {}
    def parse_value(value):
        v = value.strip().lower()
        if v in ("true", "yes", "1", "on"): return True
        if v in ("false", "no", "0", "off"): return False
        return value.strip()
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, val = line.split("=", 1)
                config[k.strip()] = parse_value(val)
    except Exception as e:
        logging.error(f"Error loading config {path}: {e}")
    return config

# --- STATUS & SPLASH SCREEN ---
def show_splash(epd):
    global SHOW_BOOT_SCREEN
    if not epd or not SHOW_BOOT_SCREEN:
        return
    splash = Image.new('L', (SCREEN_WIDTH, SCREEN_HEIGHT), COLOR_BG)
    d = ImageDraw.Draw(splash)
    cx = SCREEN_WIDTH // 2
    cy = SCREEN_HEIGHT // 2

    card_w, card_h = 440, 190
    x0, y0 = cx - card_w // 2, cy - card_h // 2
    x1, y1 = cx + card_w // 2, cy + card_h // 2
    d.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=COLOR_BG, outline=COLOR_FG, width=2)

    f_title = load_font(32, "bold")
    f_sub = load_font(18, "semibold")
    f_stat = load_font(13, "medium")

    draw_centered_text(d, cx, y0 + 30, "G4Cast Weather", f_title, COLOR_FG)
    draw_centered_text(d, cx, y0 + 76, "Connecting & Loading Forecast...", f_sub, COLOR_FG)
    d.line([(x0 + 40, y0 + 116), (x1 - 40, y0 + 116)], fill=COLOR_GRID, width=1)
    draw_centered_text(d, cx, y0 + 138, "Please wait a moment...", f_stat, COLOR_FG)

    try:
        rotated = splash.rotate(ROTATE_DEGREES)
        epd.init_fast()
        epd.display(epd.getbuffer(rotated))
    except Exception as e:
        logging.error(f"Splash screen error: {e}")

def add_status_message(msg, epd=None):
    logging.info(f"[STATUS] {msg}")

def show_error_screen(epd, title, msg):
    if not epd:
        return
    err_img = Image.new('L', (SCREEN_WIDTH, SCREEN_HEIGHT), COLOR_BG)
    d = ImageDraw.Draw(err_img)
    cx = SCREEN_WIDTH // 2
    cy = SCREEN_HEIGHT // 2

    card_w, card_h = 460, 200
    x0, y0 = cx - card_w // 2, cy - card_h // 2
    x1, y1 = cx + card_w // 2, cy + card_h // 2
    d.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=COLOR_BG, outline=COLOR_FG, width=2)

    f_title = load_font(28, "bold")
    f_msg = load_font(16, "semibold")
    f_sub = load_font(13, "medium")

    draw_centered_text(d, cx, y0 + 35, title, f_title, COLOR_FG)
    d.line([(x0 + 40, y0 + 85), (x1 - 40, y0 + 85)], fill=COLOR_GRID, width=1)
    draw_centered_text(d, cx, y0 + 115, msg, f_msg, COLOR_FG)
    draw_centered_text(d, cx, y0 + 145, "Retrying automatically...", f_sub, COLOR_FG)

    try:
        rotated = err_img.rotate(ROTATE_DEGREES)
        epd.init_fast()
        epd.display(epd.getbuffer(rotated))
    except Exception as e:
        logging.error(f"Error screen display failed: {e}")

# --- PRE-FLIGHT CHECKS ---
def wifi_up(epd):
    try:
        res = subprocess.run(["/sbin/iwgetid", "-r"], capture_output=True, text=True, check=True)
        ssid = res.stdout.strip()
        if ssid:
            add_status_message("Wi-Fi connected.", epd)
            return True
        add_status_message("Wi-Fi is not connected!", epd)
        show_error_screen(epd, "Wi-Fi Error", "Wi-Fi is not connected")
        return False
    except Exception:
        try:
            subprocess.run(["ping", "-c", "1", "-W", "2", "8.8.8.8"], check=True, stdout=subprocess.DEVNULL)
            add_status_message("Wi-Fi connected.", epd)
            return True
        except Exception:
            add_status_message("Wi-Fi check failed!", epd)
            show_error_screen(epd, "Network Error", "Internet check failed")
            return False

def city_set(epd):
    if not CITY or CITY.lower() == "city, co".lower():
        add_status_message("City is NOT set!", epd)
        show_error_screen(epd, "Config Error", "City is not set in config")
        return False
    add_status_message(f"City is set: {CITY}", epd)
    return True

def api_set(epd):
    if not API_KEY or API_KEY == "00000000000000000000000000000000":
        add_status_message("API key is NOT set!", epd)
        show_error_screen(epd, "Config Error", "OpenWeather API key is not set")
        return False
    add_status_message("API key is set.", epd)
    return True

# --- API WEATHER DATA FETCH ---
def get_forecast_data(epd=None):
    if epd: add_status_message("Fetching weather forecast...", epd)
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={CITY}&appid={API_KEY}"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            if epd: add_status_message("Weather forecast fetched.", epd)
            return res.json()
        logging.error(f"Forecast API returned {res.status_code}: {res.text}")
    except Exception as e:
        logging.error(f"Forecast API error: {e}")
        if epd: add_status_message(f"Error fetching forecast: {e}", epd)
    return None

def get_current_weather_data(epd=None):
    if epd: add_status_message("Fetching current conditions...", epd)
    url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            if epd: add_status_message("Current conditions fetched.", epd)
            return res.json()
        logging.error(f"Current weather API returned {res.status_code}: {res.text}")
    except Exception as e:
        logging.error(f"Current weather API error: {e}")
    return None

# --- NWS ACTIVE WEATHER ALERTS (FAILSAFE & CACHED) ---
NWS_CACHE_FILE = f"{base_dir}/nws_cache.json"

def get_nws_alerts(lat=33.963, lon=-117.564, tz_offset=0):
    """
    Fetch active weather alerts from the National Weather Service (NOAA).
    Failsafe:
      - Strict 6s timeout so main weather update is never blocked.
      - Graceful exception catching for timeouts, HTTP errors, or invalid JSON.
      - Cached fallback: uses cached alert if NWS temporarily fails and alert is not expired.
      - Auto-expiration: alerts past their 'ends' timestamp are discarded.
    """
    cached_alert = None
    try:
        if os.path.exists(NWS_CACHE_FILE):
            with open(NWS_CACHE_FILE, "r") as cf:
                cache_data = json.load(cf)
                exp_ts = cache_data.get("expires_ts", 0)
                if time.time() < exp_ts:
                    cached_alert = cache_data.get("banner_text")
    except Exception as e:
        logging.debug(f"NWS cache read note: {e}")

    url = f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"
    headers = {
        "User-Agent": "(G4CastWeatherStation/2.0, contact@weatherstation.local)",
        "Accept": "application/geo+json"
    }

    try:
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            features = res.json().get("features", [])
            if not features:
                if os.path.exists(NWS_CACHE_FILE):
                    try:
                        os.remove(NWS_CACHE_FILE)
                    except Exception:
                        pass
                return None

            sev_rank = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3}
            sorted_features = sorted(
                features,
                key=lambda f: sev_rank.get(f.get("properties", {}).get("severity", "Unknown"), 9)
            )

            top_alert = sorted_features[0].get("properties", {})
            event_name = top_alert.get("event", "Weather Alert").strip().upper()
            ends_raw = top_alert.get("ends")

            end_str = ""
            exp_ts = time.time() + 1800
            if ends_raw:
                try:
                    dt = datetime.fromisoformat(ends_raw.replace("Z", "+00:00")) + timedelta(seconds=tz_offset)
                    exp_ts = dt.timestamp()
                    end_str = dt.strftime("UNTIL %I %p %a").lstrip("0")
                except Exception:
                    pass

            banner_text = f"! {event_name} - {end_str}" if end_str else f"! {event_name}"

            try:
                with open(NWS_CACHE_FILE, "w") as cf:
                    json.dump({"banner_text": banner_text, "expires_ts": exp_ts}, cf)
            except Exception as e:
                logging.debug(f"NWS cache write note: {e}")

            return banner_text

        elif res.status_code in (404, 500, 502, 503, 504):
            logging.warning(f"NWS API returned {res.status_code}; using cache fallback if available.")
            return cached_alert
    except requests.exceptions.Timeout:
        logging.warning("NWS alert request timed out (6s); continuing with weather display.")
        return cached_alert
    except Exception as e:
        logging.warning(f"NWS alert fetch failed ({e}); continuing with weather display.")
        return cached_alert

    return cached_alert

# --- OPENWEATHERMAP AIR QUALITY (AQI) ---
def get_aqi_data(lat=33.963, lon=-117.564, api_key=None):
    """
    Fetch Air Quality Index (AQI) and PM2.5 from OpenWeatherMap.
    Failsafe: 5s timeout, wrapped in try/except, returns None on failure.
    """
    key = api_key or API_KEY
    if not key:
        cfg = load_config()
        key = cfg.get("API_KEY", "")
    if not key:
        return None
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {"lat": lat, "lon": lon, "appid": key}
    try:
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            item = res.json().get("list", [{}])[0]
            aqi_idx = item.get("main", {}).get("aqi", 1)
            pm25 = round(item.get("components", {}).get("pm2_5", 0))
            aqi_map = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
            label = aqi_map.get(aqi_idx, "Good")
            return f"AQI: {label}  \u2022  PM2.5: {pm25}"
    except Exception as e:
        logging.warning(f"AQI API fetch warning: {e}")
    return None

# --- CONVERSIONS ---
def c_to_f(c):
    return round(c * 9.0 / 5.0 + 32)

def mm_to_in(mm):
    return mm / 25.4

# --- CUBIC SPLINE HELPERS ---
def cubic_spline_coeffs(xs, ys):
    n = len(xs)
    a = ys.copy()
    b = [0] * (n - 1)
    d = [0] * (n - 1)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    alpha = [0] * n
    for i in range(1, n - 1):
        alpha[i] = (3 / h[i]) * (a[i + 1] - a[i]) - (3 / h[i - 1]) * (a[i] - a[i - 1])
    c = [0] * n
    l = [1] * n
    mu = [0] * n
    z = [0] * n
    for i in range(1, n - 1):
        l[i] = 2 * (xs[i + 1] - xs[i - 1]) - h[i - 1] * mu[i - 1]
        mu[i] = h[i] / l[i]
        z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i]
    for j in reversed(range(n - 1)):
        c[j] = z[j] - mu[j] * c[j + 1]
        b[j] = (a[j + 1] - a[j]) / h[j] - h[j] * (c[j + 1] + 2 * c[j]) / 3
        d[j] = (c[j + 1] - c[j]) / (3 * h[j])
    return a, b, c, d, h

def eval_spline(a, b, c, d, h, xs, x):
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            dx = x - xs[i]
            return a[i] + b[i] * dx + c[i] * dx ** 2 + d[i] * dx ** 3
    if x < xs[0]: return a[0]
    return a[-1]

def fill_graph_dither(img, xs, y_fine, plot_bottom):
    try:
        arr = np.array(img)
        x_start = int(xs[0])
        x_end = int(xs[-1])
        n_pts = len(y_fine)
        col_x = np.arange(x_start, x_end + 1)
        frac = (col_x - x_start) / max(1, (x_end - x_start)) * (n_pts - 1)
        indices = np.clip(frac.astype(int), 0, n_pts - 1)
        curve_ys = np.array(y_fine)[indices].astype(int)

        curve_grid = np.zeros(arr.shape[1], dtype=int)
        curve_grid[x_start : x_end + 1] = curve_ys

        y_idx, x_idx = np.mgrid[0 : arr.shape[0], 0 : arr.shape[1]]
        mask = (
            (x_idx >= x_start)
            & (x_idx <= x_end)
            & (y_idx >= curve_grid[None, :] + 3)
            & (y_idx < plot_bottom)
            & ((x_idx + y_idx) % 4 == 0)
        )
        arr[mask] = 140
        return Image.fromarray(arr)
    except Exception as e:
        logging.warning(f"Dither error: {e}")
        return img

# --- ICON LOADER ---
def load_weather_icon(icon_code, size=(64, 64)):
    filename = f"{icon_code}.png"
    path = os.path.join(picdir, filename)
    if os.path.exists(path):
        icon = Image.open(path).convert("RGBA")
        icon = icon.resize(size, Image.Resampling.LANCZOS)
        bg = Image.new("RGBA", size, (255, 255, 255, 255))
        composite = Image.alpha_composite(bg, icon).convert("L")
        if DARK_MODE:
            composite = Image.eval(composite, lambda px: 255 - px)
        return composite
    fallback = Image.new("L", size, COLOR_BG)
    d = ImageDraw.Draw(fallback)
    d.text((size[0]//3, size[1]//3), "?", fill=COLOR_FG)
    return fallback

# --- GLOBAL IMAGE BUFFER ---
Himage = Image.new('L', (SCREEN_WIDTH, SCREEN_HEIGHT), COLOR_BG)
draw = ImageDraw.Draw(Himage)
timebox_moved = False
card_box_coords = (16, 170, 326, 468)

# --- MODERN CLEAN DASHBOARD DRAW ---
def draw_forecast(forecast_data, current_data, alert_text=None, aqi_text=None):
    global Himage, draw
    update_colors()

    Himage = Image.new('L', (SCREEN_WIDTH, SCREEN_HEIGHT), COLOR_BG)
    draw = ImageDraw.Draw(Himage)

    # 1. CURRENT CONDITIONS
    cur_main = current_data.get("main", {})
    temp_k = cur_main.get("temp", 273.15)
    feels_k = cur_main.get("feels_like", temp_k)
    humidity = cur_main.get("humidity", 0)
    wind_speed = current_data.get("wind", {}).get("speed", 0)
    cur_weather = current_data.get("weather", [{}])[0]
    cur_icon = cur_weather.get("icon", "01d")
    cur_desc = cur_weather.get("main", "Clear").title()

    if USE_METRIC:
        cur_temp = round(temp_k - 273.15)
        cur_feels = round(feels_k - 273.15)
        wind_str = f"{round(wind_speed * 3.6)} km/h"
    else:
        cur_temp = c_to_f(temp_k - 273.15)
        cur_feels = c_to_f(feels_k - 273.15)
        wind_str = f"{round(wind_speed * 2.237)} mph"

    city_name = DISPLAY_TEXT if DISPLAY_TEXT else current_data.get("name", "Weather").split(",")[0]

    tz_offset = current_data.get("timezone", 0)
    utc_now = datetime.now(timezone.utc)
    local_dt = utc_now + timedelta(seconds=tz_offset)

    if USE_24HFORMAT:
        time_str = local_dt.strftime("%H:%M")
        ampm_str = ""
    else:
        time_str = local_dt.strftime("%I:%M").lstrip("0")
        ampm_str = local_dt.strftime("%p")
    date_str = local_dt.strftime("%A, %b %d")

    # 2. 5-DAY FORECAST
    daily_buckets = {}
    hourly_entries = []
    forecast_list = forecast_data.get("list", [])

    for item in forecast_list:
        dt_txt = item.get("dt_txt")
        item_dt = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S") + timedelta(seconds=tz_offset)
        day_key = item_dt.strftime("%Y-%m-%d")
        t_c = item["main"]["temp"] - 273.15
        t_val = t_c if USE_METRIC else c_to_f(t_c)
        rain_val = item.get("rain", {}).get("3h", 0)
        pop_val = item.get("pop", 0)

        if len(hourly_entries) < 8:
            hourly_entries.append((item_dt, t_val, rain_val, pop_val))

        if day_key not in daily_buckets:
            daily_buckets[day_key] = {"dt": item_dt, "temps": [], "icons": []}
        daily_buckets[day_key]["temps"].append(t_val)
        daily_buckets[day_key]["icons"].append(item["weather"][0]["icon"])

    sorted_days = sorted(daily_buckets.keys())[:5]
    days_data = []
    today_high, today_low = cur_temp, cur_temp

    for i, d_k in enumerate(sorted_days):
        b = daily_buckets[d_k]
        day_icons = [ic for ic in b["icons"] if ic.endswith("d")]
        if day_icons:
            icon_pick = max(set(day_icons), key=day_icons.count)
        else:
            icon_pick = max(set(b["icons"]), key=b["icons"].count).replace("n", "d")

        day_name = b["dt"].strftime("%a").upper()
        is_today = (b["dt"].date() == local_dt.date()) or (i == 0)
        h_val = round(max(b["temps"]))
        l_val = round(min(b["temps"]))
        if is_today:
            day_name = "TODAY"
            today_high = max(cur_temp, h_val)
            today_low = min(cur_temp, l_val)

        days_data.append({
            "name": day_name,
            "is_today": is_today,
            "high": h_val,
            "low": l_val,
            "icon": icon_pick
        })

    # =========================================================================
    # SECTION 1: TOP 5-DAY FORECAST BAR
    # =========================================================================
    num_days = len(days_data)
    if num_days > 0:
        bar_left = 16
        bar_right = SCREEN_WIDTH - 16
        col_w = (bar_right - bar_left) // num_days

        for i, d in enumerate(days_data):
            cx = bar_left + i * col_w + col_w // 2
            f_day = load_font(18, "bold")
            draw_centered_text(draw, cx, 14, d["name"], f_day, COLOR_FG)

            icon_img = load_weather_icon(d["icon"], size=(60, 60))
            Himage.paste(icon_img, (cx - 30, 42))

            f_hl = load_font(20, "bold")
            hl_str = f"{d['high']}{DEG}  {d['low']}{DEG}"
            draw_centered_text(draw, cx, 114, hl_str, f_hl, COLOR_FG)

            if i < num_days - 1:
                div_x = bar_left + (i + 1) * col_w
                draw.line([(div_x, 18), (div_x, 142)], fill=COLOR_LINE, width=1)

    draw.line([(16, 156), (SCREEN_WIDTH - 16, 156)], fill=COLOR_FG, width=2)

    # =========================================================================
    # SECTION 2: LEFT HERO (SOLID INVERTED BLACK CARD)
    # =========================================================================
    c_x0, c_y0 = 16, 170
    c_w, c_h = 310, 298
    c_x1, c_y1 = c_x0 + c_w, c_y0 + c_h
    c_cx = c_x0 + c_w // 2
    draw.rounded_rectangle([c_x0, c_y0, c_x1, c_y1], radius=16, fill=COLOR_FG, outline=COLOR_FG, width=2)

    # White typography on solid black card
    f_city_inv = load_font(24, "bold")
    draw_centered_text(draw, c_cx, c_y0 + 14, city_name.upper(), f_city_inv, COLOR_BG)
    draw_centered_text(draw, c_cx, c_y0 + 44, date_str, load_font(15, "bold"), COLOR_BG)

    # Inverted weather icon (white on black)
    inv_icon = load_weather_icon(cur_icon, size=(58, 58))
    inv_icon = Image.eval(inv_icon.convert("L"), lambda px: 255 - px)
    f_ht_inv = load_font(68, "bold")
    t_str = f"{cur_temp}{DEG}"
    tw, _ = text_size(draw, t_str, f_ht_inv)
    b_w = 58 + 10 + tw
    b_sx = c_cx - b_w // 2
    Himage.paste(inv_icon, (b_sx, c_y0 + 68))
    draw.text((b_sx + 58 + 10, c_y0 + 62), t_str, font=f_ht_inv, fill=COLOR_BG)

    draw_centered_text(draw, c_cx, c_y0 + 138, f"{cur_desc.upper()}  \u2022  H {today_high}{DEG}  L {today_low}{DEG}", load_font(16, "bold"), COLOR_BG)
    draw_centered_text(draw, c_cx, c_y0 + 162, f"Humidity {humidity}%   Wind {wind_str}", load_font(14, "bold"), COLOR_BG)
    draw_centered_text(draw, c_cx, c_y0 + 184, f"AQI: {aqi_text.upper() if aqi_text else 'GOOD'}", load_font(14, "bold"), COLOR_BG)

    draw.line([(c_x0 + 18, c_y0 + 206), (c_x1 - 18, c_y0 + 206)], fill=COLOR_BG, width=1)

    # Inverted Clock
    f_clk_inv = load_font(50, "bold")
    f_apm_inv = load_font(20, "bold")
    cw, _ = text_size(draw, time_str, f_clk_inv)
    aw, _ = text_size(draw, ampm_str, f_apm_inv)
    csx = c_cx - (cw + 8 + aw) // 2
    draw.text((csx, c_y0 + 224), time_str, font=f_clk_inv, fill=COLOR_BG)
    if ampm_str:
        draw.text((csx + cw + 8, c_y0 + 242), ampm_str, font=f_apm_inv, fill=COLOR_BG)

    # =========================================================================
    # SECTION 3: RIGHT GRAPH CARD
    # =========================================================================
    g_x0 = 342
    g_w = SCREEN_WIDTH - g_x0 - 16
    g_x1, g_y1 = g_x0 + g_w, c_y0 + 298
    draw.rounded_rectangle([g_x0, c_y0, g_x1, g_y1], radius=16, fill=COLOR_BG, outline=COLOR_FG, width=2)
    draw.text((g_x0 + 20, c_y0 + 14), "24-HOUR FORECAST", font=load_font(15, "bold"), fill=COLOR_FG)
    draw.text((g_x1 - 130, c_y0 + 16), f"UPDATED {time_str} {ampm_str}", font=load_font(12, "semibold"), fill=COLOR_FG)

    p_left, p_right = g_x0 + 28, g_x1 - 28
    p_top, p_bot = c_y0 + 64, g_y1 - 62
    p_w, p_h = p_right - p_left, p_bot - p_top

    if len(hourly_entries) >= 4:
        temps = [t for _, t, _, _ in hourly_entries]
        min_t, max_t = min(temps), max(temps)
        t_range = max_t - min_t if max_t != min_t else 2

        t_pad = max(2.0, t_range * 0.25)
        plot_min_t = min_t - t_pad
        plot_max_t = max_t + t_pad
        effective_range = plot_max_t - plot_min_t

        n_pts = len(hourly_entries)
        xs, ys = [], []
        for i in range(n_pts):
            px = p_left + int(i * (p_w / (n_pts - 1)))
            py = int(p_bot - ((temps[i] - plot_min_t) / effective_range) * p_h)
            xs.append(px)
            ys.append(py)

        # Smooth Cubic Spline Curve & Dither Area Fill
        try:
            a, b, c, d_s, h = cubic_spline_coeffs(xs, ys)
            xf = np.linspace(xs[0], xs[-1], 200)
            yf = [eval_spline(a, b, c, d_s, h, xs, xi) for xi in xf]

            Himage = fill_graph_dither(Himage, xs, yf, p_bot)
            draw = ImageDraw.Draw(Himage)

            for k in range(len(xf) - 1):
                draw.line([(xf[k], yf[k]), (xf[k + 1], yf[k + 1])], fill=COLOR_FG, width=3)
        except Exception:
            for k in range(len(xs) - 1):
                draw.line([(xs[k], ys[k]), (xs[k + 1], ys[k + 1])], fill=COLOR_FG, width=3)

        # Baseline axis
        draw.line([(p_left - 10, p_bot), (p_right + 10, p_bot)], fill=COLOR_FG, width=2)

        f_temp_lbl = load_font(16, "bold")
        f_hour_lbl = load_font(13, "bold")
        f_pop_lbl = load_font(12, "bold")

        for i, (item_dt, t_val, rain_mm, pop_val) in enumerate(hourly_entries):
            px, py = xs[i], ys[i]
            draw_centered_text(draw, px, py - 24, f"{round(t_val)}{DEG}", f_temp_lbl, COLOR_FG)

            r = 5
            draw.ellipse([px - r, py - r, px + r, py + r], fill=COLOR_FG)
            draw.ellipse([px - r + 2, py - r + 2, px + r - 2, py + r - 2], fill=COLOR_BG)

            if i == 0:
                h_str = "NOW"
            else:
                h_str = item_dt.strftime("%H:%M") if USE_24HFORMAT else item_dt.strftime("%I %p").lstrip("0")

            draw_centered_text(draw, px, p_bot + 8, h_str, f_hour_lbl, COLOR_FG)

            # Precipitation badge if pop >= 15%
            pop_pct = int(pop_val * 100) if pop_val else 0
            if pop_pct >= 15:
                pop_txt = f"{pop_pct}%"
                pw, _ = text_size(draw, pop_txt, f_pop_lbl)
                drop_total_w = 8 + 3 + pw
                start_x = px - drop_total_w // 2
                draw_droplet(draw, start_x + 3, p_bot + 34, size=7, fill=COLOR_FG)
                draw.text((start_x + 10, p_bot + 27), pop_txt, font=f_pop_lbl, fill=COLOR_FG)

    # ACTIVE SEVERE WEATHER / NWS ADVISORY BANNER
    if alert_text:
        pill_x0 = g_x0
        pill_x1 = g_x1
        pill_y0 = SCREEN_HEIGHT - 28
        pill_y1 = SCREEN_HEIGHT - 6
        draw.rounded_rectangle([pill_x0, pill_y0, pill_x1, pill_y1], radius=6, fill=COLOR_FG)

        f_alert = load_font(12, "bold")
        max_w = (pill_x1 - pill_x0) - 20
        display_alert = alert_text
        while text_size(draw, display_alert, f_alert)[0] > max_w and len(display_alert) > 10:
            display_alert = display_alert[:-4] + "..."

        aw, ah = text_size(draw, display_alert, f_alert)
        draw.text(
            ((pill_x0 + pill_x1) // 2 - aw // 2, (pill_y0 + pill_y1) // 2 - ah // 2 - 1),
            display_alert,
            font=f_alert,
            fill=COLOR_BG
        )

    return Himage

# --- MINUTE CLOCK UPDATE (PARTIAL REFRESH) ---
def update_time(epd, utc_offset_seconds):
    global Himage, draw
    # Option 2: Clear inverted clock area inside black card
    c_x0, c_y0, c_w = 16, 170, 310
    c_cx = c_x0 + c_w // 2
    draw.rectangle([c_x0 + 10, c_y0 + 215, c_x0 + c_w - 10, c_y0 + 285], fill=COLOR_FG)

    utc_now = datetime.now(timezone.utc)
    local_dt = utc_now + timedelta(seconds=utc_offset_seconds)
    if USE_24HFORMAT:
        time_str = local_dt.strftime("%H:%M")
        ampm_str = ""
    else:
        time_str = local_dt.strftime("%I:%M").lstrip("0")
        ampm_str = local_dt.strftime("%p")

    f_clk_inv = load_font(50, "bold")
    f_apm_inv = load_font(20, "bold")
    cw, _ = text_size(draw, time_str, f_clk_inv)
    aw, _ = text_size(draw, ampm_str, f_apm_inv)
    csx = c_cx - (cw + 8 + aw) // 2
    draw.text((csx, c_y0 + 224), time_str, font=f_clk_inv, fill=COLOR_BG)
    if ampm_str:
        draw.text((csx + cw + 8, c_y0 + 242), ampm_str, font=f_apm_inv, fill=COLOR_BG)

    if epd:
        try:
            Himage_1bit = Himage.convert("1", dither=Image.Dither.NONE)
            epd.displayPartial_Quick(epd.getbuffer(Himage_1bit))
            epd.sleep()
        except Exception as e:
            logging.error(f"Partial time refresh error: {e}")
def update_display(epd, img):
    global refresh_count, SHOW_BOOT_SCREEN
    if not epd:
        return
    try:
        rotated = img.rotate(ROTATE_DEGREES)
        buf = epd.getbuffer(rotated)

        # Smart refresh: fast waveform (~1.8s) for smooth routine updates;
        # full refresh (~4.5s) once every 24 cycles (~12 hours) to recalibrate microcapsules
        if refresh_count > 0 and refresh_count % 24 == 0:
            logging.info(f"Performing maintenance full refresh (cycle {refresh_count})...")
            epd.init()
        else:
            logging.info(f"Performing fast refresh (cycle {refresh_count})...")
            epd.init_fast()

        epd.display(buf)
        SHOW_BOOT_SCREEN = False
        refresh_count += 1
        epd.sleep()
        logging.info(f"Display update complete (cycle {refresh_count})")
    except Exception as e:
        logging.error(f"Display update error: {e}")

# --- MAIN CONTROLLER ---
def main():
    global epd, CITY, API_KEY, USE_METRIC, DISPLAY_TEXT, DARK_MODE, USE_24HFORMAT, USE_AVGTEMP
    global SHOW_BOOT_SCREEN, utc_offset_seconds

    cfg = load_config()
    CITY = cfg.get("CITY", "")
    API_KEY = cfg.get("API_KEY", "")
    USE_METRIC = cfg.get("USE_METRIC", False)
    DISPLAY_TEXT = cfg.get("DISPLAY_TEXT", "")
    DARK_MODE = cfg.get("DARK_MODE", False)
    USE_24HFORMAT = cfg.get("USE_24HFORMAT", False)
    USE_AVGTEMP = cfg.get("USE_AVGTEMP", False)
    update_colors()

    if epd is None and epd7in5_V2:
        try:
            epd = epd7in5_V2.EPD()
        except Exception as e:
            logging.error(f"EPD initialization error: {e}")

    # Show sleek splash screen once on cold boot
    if SHOW_BOOT_SCREEN:
        show_splash(epd)

    if not wifi_up(epd): return
    if not city_set(epd): return
    if not api_set(epd): return

    forecast_data = get_forecast_data(epd)
    current_data = get_current_weather_data(epd)

    if not forecast_data or not current_data:
        add_status_message("Weather API error. Retrying in 60s...")
        return

    add_status_message("G4Cast: Rendering clean layout...")
    utc_offset_seconds = current_data.get("timezone", 0)
    coords = current_data.get("coord", {})
    lat = coords.get("lat", 33.963)
    lon = coords.get("lon", -117.564)

    # Fetch active NWS alerts (failsafe: strict 6s timeout, cached, never blocks)
    active_alert = None
    try:
        active_alert = get_nws_alerts(lat, lon, utc_offset_seconds)
    except Exception as e:
        logging.warning(f"Unexpected NWS alert error: {e}")

    # Fetch Air Quality Index (AQI) (failsafe: 5s timeout, never blocks)
    aqi_str = None
    try:
        aqi_str = get_aqi_data(lat, lon)
    except Exception as e:
        logging.warning(f"Unexpected AQI error: {e}")

    img = draw_forecast(forecast_data, current_data, alert_text=active_alert, aqi_text=aqi_str)
    update_display(epd, img)

if __name__ == "__main__":
    main()

    try:
        update_time(epd, utc_offset_seconds)
    except Exception:
        pass

    time.sleep(60)

    while True:
        now = datetime.now()
        minute = now.minute

        if minute % 30 == 0:
            main()

        if minute % 60 == 0:
            timebox_moved = not timebox_moved

        try:
            update_time(epd, utc_offset_seconds)
        except Exception as e:
            logging.error(f"Clock loop error: {e}")

        time.sleep(60)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modern UI Renderer for G4Cast 7.5-inch E-Ink Display (800x480)
Featuring Inter typography, refined layout hierarchy, and clean charts.
"""

import os
import sys
import json
import math
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# --- SCREEN DIMENSIONS ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
ROTATE_DEGREES = 180

# --- FONT CONFIGURATION ---
FONT_DIR = "/usr/share/fonts/opentype/inter"
FONTS = {
    "bold": f"{FONT_DIR}/Inter-Bold.otf",
    "semibold": f"{FONT_DIR}/Inter-SemiBold.otf",
    "medium": f"{FONT_DIR}/Inter-Medium.otf",
    "regular": f"{FONT_DIR}/Inter-Regular.otf",
    "fallback": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
}

def get_font(weight="medium", size=18):
    path = FONTS.get(weight, FONTS["medium"])
    try:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
        elif os.path.exists(FONTS["fallback"]):
            return ImageFont.truetype(FONTS["fallback"], size)
    except Exception:
        pass
    return ImageFont.load_default()

def text_dims(draw, text, font):
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), str(text), font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    return draw.textsize(str(text), font=font)

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
    if x < xs[0]:
        return a[0]
    return a[-1]

# --- ICON LOADER ---
def load_weather_icon(icon_code, size=(80, 80), dark_mode=False, pic_dir="/home/user/G4Cast/pic"):
    filename = f"{icon_code}.png"
    path = os.path.join(pic_dir, filename)
    if os.path.exists(path):
        icon = Image.open(path).convert("RGBA")
        icon = icon.resize(size, Image.Resampling.LANCZOS)
        bg = Image.new("RGBA", size, (255, 255, 255, 255))
        composite = Image.alpha_composite(bg, icon).convert("L")
        if dark_mode:
            composite = Image.eval(composite, lambda px: 255 - px)
        return composite
    fallback = Image.new("L", size, 0 if dark_mode else 255)
    d = ImageDraw.Draw(fallback)
    d.text((size[0]//3, size[1]//3), "?", fill=255 if dark_mode else 0)
    return fallback

# --- MAIN MODERN RENDER FUNCTION ---
def render_dashboard(current_data, forecast_data, config, now_dt=None):
    dark_mode = config.get("DARK_MODE", "False").lower() in ("true", "1", "yes")
    use_metric = config.get("USE_METRIC", "False").lower() in ("true", "1", "yes")
    use_24h = config.get("USE_24HFORMAT", "False").lower() in ("true", "1", "yes")
    display_text = config.get("DISPLAY_TEXT", "").strip()

    c_bg = 0 if dark_mode else 255
    c_fg = 255 if dark_mode else 0
    c_sub = 180 if dark_mode else 90
    c_muted = 130 if dark_mode else 160
    c_grid = 70 if dark_mode else 225

    img = Image.new("L", (SCREEN_WIDTH, SCREEN_HEIGHT), c_bg)
    draw = ImageDraw.Draw(img)

    # 1. PARSE CURRENT WEATHER
    cur_main = current_data.get("main", {})
    temp_k = cur_main.get("temp", 273.15)
    feels_k = cur_main.get("feels_like", temp_k)
    humidity = cur_main.get("humidity", 0)
    wind_speed = current_data.get("wind", {}).get("speed", 0)
    cur_weather = current_data.get("weather", [{}])[0]
    cur_icon = cur_weather.get("icon", "01d")
    cur_desc = cur_weather.get("main", "Clear").title()

    if use_metric:
        cur_temp = round(temp_k - 273.15)
        cur_feels = round(feels_k - 273.15)
        unit = "°"
        wind_str = f"{round(wind_speed * 3.6)} km/h"
    else:
        cur_temp = c_to_f(temp_k - 273.15)
        cur_feels = c_to_f(feels_k - 273.15)
        unit = "°"
        wind_str = f"{round(wind_speed * 2.237)} mph"

    city_name = display_text if display_text else current_data.get("name", "Weather").split(",")[0]

    tz_offset = current_data.get("timezone", 0)
    if now_dt is None:
        utc_now = datetime.now(timezone.utc)
        local_dt = utc_now + timedelta(seconds=tz_offset)
    else:
        local_dt = now_dt

    if use_24h:
        time_str = local_dt.strftime("%H:%M")
        ampm_str = ""
    else:
        time_str = local_dt.strftime("%I:%M").lstrip("0")
        ampm_str = local_dt.strftime("%p")
    date_str = local_dt.strftime("%a, %b %d").upper()

    # 2. PARSE 5-DAY FORECAST
    daily_buckets = {}
    hourly_entries = []

    forecast_list = forecast_data.get("list", [])

    for item in forecast_list:
        dt_txt = item.get("dt_txt")
        item_dt = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S") + timedelta(seconds=tz_offset)
        day_key = item_dt.strftime("%Y-%m-%d")
        t_c = item["main"]["temp"] - 273.15
        t_val = t_c if use_metric else c_to_f(t_c)
        rain_val = item.get("rain", {}).get("3h", 0)

        if len(hourly_entries) < 8:
            hourly_entries.append((item_dt, t_val, rain_val))

        if day_key not in daily_buckets:
            daily_buckets[day_key] = {
                "dt": item_dt,
                "temps": [],
                "icons": [],
                "rain": 0
            }
        daily_buckets[day_key]["temps"].append(t_val)
        daily_buckets[day_key]["icons"].append(item["weather"][0]["icon"])

    sorted_days = sorted(daily_buckets.keys())[:5]
    days_data = []
    for d_k in sorted_days:
        b = daily_buckets[d_k]
        # Prefer daytime icon (e.g., ending with 'd' or from midday)
        day_icons = [ic for ic in b["icons"] if ic.endswith("d")]
        if day_icons:
            icon_pick = max(set(day_icons), key=day_icons.count)
        else:
            # Fallback to replacing 'n' with 'd' so daily forecast shows daytime weather
            most_common = max(set(b["icons"]), key=b["icons"].count)
            icon_pick = most_common.replace("n", "d")

        day_name = b["dt"].strftime("%a").upper()
        if b["dt"].date() == local_dt.date():
            day_name = "TODAY"
        days_data.append({
            "name": day_name,
            "high": round(max(b["temps"])),
            "low": round(min(b["temps"])),
            "icon": icon_pick
        })

    # =========================================================================
    # SECTION 1: TOP 5-DAY FORECAST BAR (y: 12 to 155)
    # =========================================================================
    num_days = len(days_data)
    if num_days > 0:
        day_col_w = (SCREEN_WIDTH - 32) // num_days
        for i, d in enumerate(days_data):
            cx = 16 + i * day_col_w + day_col_w // 2

            # Day label
            f_day = get_font("semibold", 14)
            w, h = text_dims(draw, d["name"], f_day)
            draw.text((cx - w // 2, 14), d["name"], font=f_day, fill=c_fg)

            # Weather Icon
            icon_img = load_weather_icon(d["icon"], size=(64, 64), dark_mode=dark_mode)
            img.paste(icon_img, (cx - 32, 38))

            # High / Low temperatures
            f_high = get_font("bold", 20)
            f_low = get_font("medium", 16)
            f_sep = get_font("regular", 14)

            high_str = f"{d['high']}{unit}"
            low_str = f"{d['low']}{unit}"

            w_h, _ = text_dims(draw, high_str, f_high)
            w_sep, _ = text_dims(draw, "·", f_sep)
            w_l, _ = text_dims(draw, low_str, f_low)
            total_w = w_h + 6 + w_sep + 6 + w_l

            start_x = cx - total_w // 2
            draw.text((start_x, 114), high_str, font=f_high, fill=c_fg)
            draw.text((start_x + w_h + 6, 116), "·", font=f_sep, fill=c_sub)
            draw.text((start_x + w_h + 6 + w_sep + 6, 117), low_str, font=f_low, fill=c_sub)

            # Column dividers
            if i < num_days - 1:
                div_x = 16 + (i + 1) * day_col_w
                draw.line([(div_x, 20), (div_x, 140)], fill=c_grid, width=1)

    # Horizontal Divider Line
    draw.line([(16, 155), (SCREEN_WIDTH - 16, 155)], fill=c_muted, width=1)

    # =========================================================================
    # SECTION 2: LEFT HERO CARD - CURRENT CONDITIONS & CLOCK (x: 16 to 220, y: 170 to 465)
    # =========================================================================
    card_x0, card_y0 = 16, 170
    card_w, card_h = 205, 295
    card_x1, card_y1 = card_x0 + card_w, card_y0 + card_h

    # Card border
    draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=12, fill=c_bg, outline=c_fg, width=2)

    # City & Date Header
    f_city = get_font("bold", 20)
    draw.text((card_x0 + 16, card_y0 + 14), city_name, font=f_city, fill=c_fg)

    f_date = get_font("medium", 11)
    draw.text((card_x0 + 16, card_y0 + 38), date_str, font=f_date, fill=c_sub)

    # Hero Temp & Icon
    f_hero_temp = get_font("bold", 54)
    temp_display = f"{cur_temp}{unit}"

    hero_icon = load_weather_icon(cur_icon, size=(54, 54), dark_mode=dark_mode)
    img.paste(hero_icon, (card_x0 + 14, card_y0 + 64))
    draw.text((card_x0 + 78, card_y0 + 60), temp_display, font=f_hero_temp, fill=c_fg)

    # Condition & Feels Like
    f_desc = get_font("semibold", 15)
    draw.text((card_x0 + 16, card_y0 + 126), cur_desc, font=f_desc, fill=c_fg)

    f_stats = get_font("regular", 13)
    feels_str = f"Feels like {cur_feels}{unit}"
    draw.text((card_x0 + 16, card_y0 + 148), feels_str, font=f_stats, fill=c_sub)

    # Secondary Stats: Humidity & Wind
    meta_str = f"Humidity: {humidity}%  ·  Wind: {wind_str}"
    f_meta = get_font("regular", 11)
    draw.text((card_x0 + 16, card_y0 + 172), meta_str, font=f_meta, fill=c_sub)

    # Internal divider for time
    draw.line([(card_x0 + 12, card_y0 + 202), (card_x1 - 12, card_y0 + 202)], fill=c_grid, width=1)

    # Digital Clock
    f_clock = get_font("bold", 40)
    f_ampm = get_font("semibold", 16)
    w_clock, _ = text_dims(draw, time_str, f_clock)
    w_ampm, _ = text_dims(draw, ampm_str, f_ampm)

    clock_total_w = w_clock + (6 + w_ampm if ampm_str else 0)
    clock_start_x = card_x0 + (card_w - clock_total_w) // 2

    draw.text((clock_start_x, card_y0 + 224), time_str, font=f_clock, fill=c_fg)
    if ampm_str:
        draw.text((clock_start_x + w_clock + 6, card_y0 + 234), ampm_str, font=f_ampm, fill=c_sub)

    # =========================================================================
    # SECTION 3: HOURLY TEMPERATURE GRAPH (x: 236 to 784, y: 170 to 465)
    # =========================================================================
    g_x0, g_y0 = 236, 170
    g_w, g_h = SCREEN_WIDTH - g_x0 - 16, 295
    g_x1, g_y1 = g_x0 + g_w, g_y0 + g_h

    draw.rounded_rectangle([g_x0, g_y0, g_x1, g_y1], radius=12, fill=c_bg, outline=c_muted, width=1)

    f_ghdr = get_font("semibold", 12)
    draw.text((g_x0 + 16, g_y0 + 14), "24-HOUR FORECAST", font=f_ghdr, fill=c_sub)

    plot_left = g_x0 + 36
    plot_right = g_x1 - 36
    plot_top = g_y0 + 64
    plot_bottom = g_y1 - 56
    plot_w = plot_right - plot_left
    plot_h = plot_bottom - plot_top

    if len(hourly_entries) >= 4:
        temps = [t for _, t, _ in hourly_entries]
        min_t, max_t = min(temps), max(temps)
        t_range = max_t - min_t if max_t != min_t else 2

        t_pad = max(1.5, t_range * 0.22)
        plot_min_t = min_t - t_pad
        plot_max_t = max_t + t_pad
        effective_range = plot_max_t - plot_min_t

        n_pts = len(hourly_entries)
        xs = [plot_left + int(i * (plot_w / (n_pts - 1))) for i in range(n_pts)]
        ys = [int(plot_bottom - ((t - plot_min_t) / effective_range) * plot_h) for t in temps]

        # Horizontal Gridlines (Min & Max reference)
        for grid_val in (min_t, max_t):
            gy = int(plot_bottom - ((grid_val - plot_min_t) / effective_range) * plot_h)
            dash_len = 6
            gap_len = 4
            x_curr = plot_left - 10
            while x_curr < plot_right + 10:
                draw.line([(x_curr, gy), (min(x_curr + dash_len, plot_right + 10), gy)], fill=c_grid, width=1)
                x_curr += dash_len + gap_len

        # Smooth Cubic Spline Line
        try:
            a, b, c, d, h = cubic_spline_coeffs(xs, ys)
            x_fine = np.linspace(xs[0], xs[-1], 250)
            y_fine = [eval_spline(a, b, c, d, h, xs, xi) for xi in x_fine]

            for k in range(len(x_fine) - 1):
                draw.line([(x_fine[k], y_fine[k]), (x_fine[k + 1], y_fine[k + 1])], fill=c_fg, width=3)
        except Exception:
            for k in range(len(xs) - 1):
                draw.line([(xs[k], ys[k]), (xs[k + 1], ys[k + 1])], fill=c_fg, width=3)

        f_temp_lbl = get_font("bold", 15)
        f_hour_lbl = get_font("medium", 12)
        f_rain_lbl = get_font("regular", 10)

        for i, (item_dt, t_val, rain_val) in enumerate(hourly_entries):
            px, py = xs[i], ys[i]

            # Temperature Label
            t_str = f"{round(t_val)}{unit}"
            tw, th = text_dims(draw, t_str, f_temp_lbl)
            draw.text((px - tw // 2, py - th - 10), t_str, font=f_temp_lbl, fill=c_fg)

            # Sleek hollow node
            r = 5
            draw.ellipse([px - r, py - r, px + r, py + r], fill=c_fg)
            draw.ellipse([px - r + 2, py - r + 2, px + r - 2, py + r - 2], fill=c_bg)

            # Vertical guide line
            draw.line([(px, py + r + 2), (px, plot_bottom + 6)], fill=c_grid, width=1)

            # Hour label
            if i == 0:
                h_str = "NOW"
            else:
                if use_24h:
                    h_str = item_dt.strftime("%H:%M")
                else:
                    h_str = item_dt.strftime("%I %p").lstrip("0")

            hw, hh = text_dims(draw, h_str, f_hour_lbl)
            draw.text((px - hw // 2, plot_bottom + 12), h_str, font=f_hour_lbl, fill=c_sub)

            # Rain indicator
            if rain_val and rain_val > 0.1:
                rain_str = f"{round(rain_val, 1)}mm" if use_metric else f"{round(mm_to_in(rain_val), 2)}in"
                rw, rh = text_dims(draw, rain_str, f_rain_lbl)
                draw.text((px - rw // 2, plot_bottom + 30), rain_str, font=f_rain_lbl, fill=c_fg)

    return img

if __name__ == "__main__":
    cache_path = "/home/user/G4Cast/weather_cache.json"
    with open(cache_path) as f:
        data = json.load(f)

    cfg = {}
    with open("/boot/firmware/G4Cast/G4CastData.txt") as f:
        for line in f:
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()

    img = render_dashboard(data["current"], data["forecast"], cfg)
    img.save("/home/user/G4Cast/preview.png")
    print("Preview image generated at /home/user/G4Cast/preview.png")

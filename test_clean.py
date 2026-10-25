# -*- coding: utf-8 -*-
import os
import sys
import json
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
import numpy as np

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
ROTATE_DEGREES = 180

FONT_DIR = "/usr/share/fonts/opentype/inter"
FONTS = {
    "bold": f"{FONT_DIR}/Inter-Bold.otf",
    "semibold": f"{FONT_DIR}/Inter-SemiBold.otf",
    "medium": f"{FONT_DIR}/Inter-Medium.otf",
    "regular": f"{FONT_DIR}/Inter-Regular.otf",
    "fallback": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
}

DEG = "\u00b0"

def get_font(weight="bold", size=18):
    path = FONTS.get(weight, FONTS["bold"])
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

def draw_centered_text(draw, cx, y, text, font, fill):
    w, h = text_dims(draw, text, font)
    draw.text((cx - w // 2, y), text, font=font, fill=fill)
    return w, h

def c_to_f(c):
    return round(c * 9.0 / 5.0 + 32)

def mm_to_in(mm):
    return mm / 25.4

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

def load_weather_icon(icon_code, size=(66, 66), dark_mode=False, pic_dir="/home/user/G4Cast/pic"):
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

def render_dashboard(current_data, forecast_data, config, now_dt=None):
    dark_mode = config.get("DARK_MODE", "False").lower() in ("true", "1", "yes")
    use_metric = config.get("USE_METRIC", "False").lower() in ("true", "1", "yes")
    use_24h = config.get("USE_24HFORMAT", "False").lower() in ("true", "1", "yes")
    display_text = config.get("DISPLAY_TEXT", "").strip()

    c_bg = 0 if dark_mode else 255
    c_fg = 255 if dark_mode else 0
    c_line = 180 if dark_mode else 90
    c_grid = 110 if dark_mode else 190

    img = Image.new("L", (SCREEN_WIDTH, SCREEN_HEIGHT), c_bg)
    draw = ImageDraw.Draw(img)

    # Weather data extraction
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
        wind_str = f"{round(wind_speed * 3.6)} km/h"
    else:
        cur_temp = c_to_f(temp_k - 273.15)
        cur_feels = c_to_f(feels_k - 273.15)
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
    date_str = local_dt.strftime("%A, %b %d")

    # 5-Day forecast aggregation
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
    # SECTION 1: TOP 5-DAY FORECAST BAR (Height: 155px) - PERFECTLY CENTERED
    # =========================================================================
    num_days = len(days_data)
    if num_days > 0:
        bar_left = 16
        bar_right = SCREEN_WIDTH - 16
        col_w = (bar_right - bar_left) // num_days

        for i, d in enumerate(days_data):
            # Center x of this day column
            cx = bar_left + i * col_w + col_w // 2

            # Day label: Bold, perfectly centered
            f_day = get_font("bold", 18)
            draw_centered_text(draw, cx, 14, d["name"], f_day, c_fg)

            # Weather Icon: 64x64, perfectly centered
            icon_img = load_weather_icon(d["icon"], size=(64, 64), dark_mode=dark_mode)
            img.paste(icon_img, (cx - 32, 42))

            # High / Low: Centered clean text
            f_hl = get_font("bold", 22)
            hl_str = f"{d['high']}{DEG}  {d['low']}{DEG}"
            draw_centered_text(draw, cx, 114, hl_str, f_hl, c_fg)

            # Clean vertical separator lines between columns
            if i < num_days - 1:
                div_x = bar_left + (i + 1) * col_w
                draw.line([(div_x, 18), (div_x, 142)], fill=c_line, width=1)

    # Main Horizontal Divider Line across the full screen
    draw.line([(16, 156), (SCREEN_WIDTH - 16, 156)], fill=c_fg, width=2)

    # =========================================================================
    # SECTION 2: LEFT HERO CARD (Width: 230px, Height: 304px) - CLEAN & CENTERED
    # =========================================================================
    card_x0, card_y0 = 16, 170
    card_w, card_h = 230, 298
    card_x1, card_y1 = card_x0 + card_w, card_y0 + card_h
    card_cx = card_x0 + card_w // 2

    # Card border with rounded corners
    draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=14, fill=c_bg, outline=c_fg, width=2)

    # 1. City Name: Centered, Bold 24pt
    f_city = get_font("bold", 24)
    draw_centered_text(draw, card_cx, card_y0 + 14, city_name, f_city, c_fg)

    # 2. Date: Centered, Medium 13pt
    f_date = get_font("semibold", 13)
    draw_centered_text(draw, card_cx, card_y0 + 44, date_str, f_date, c_fg)

    # 3. Hero Temperature & Condition Icon: Perfectly Centered Block
    f_hero_temp = get_font("bold", 62)
    temp_str = f"{cur_temp}{DEG}"
    tw, th = text_dims(draw, temp_str, f_hero_temp)

    # Pair 54x54 icon and temp side-by-side centered
    hero_icon = load_weather_icon(cur_icon, size=(54, 54), dark_mode=dark_mode)
    block_w = 54 + 10 + tw
    block_start_x = card_cx - block_w // 2
    img.paste(hero_icon, (block_start_x, card_y0 + 68))
    draw.text((block_start_x + 54 + 10, card_y0 + 62), temp_str, font=f_hero_temp, fill=c_fg)

    # 4. Condition & High/Low: Centered Single Clean Line
    f_sub = get_font("bold", 15)
    sub_str = f"{cur_desc}  \u2022  H: {today_high}{DEG}  L: {today_low}{DEG}"
    draw_centered_text(draw, card_cx, card_y0 + 134, sub_str, f_sub, c_fg)

    # 5. Humidity & Wind: Centered Single Clean Line
    f_meta = get_font("semibold", 13)
    meta_str = f"Humidity {humidity}%   Wind {wind_str}"
    draw_centered_text(draw, card_cx, card_y0 + 160, meta_str, f_meta, c_fg)

    # Clean Divider inside card
    draw.line([(card_x0 + 16, card_y0 + 196), (card_x1 - 16, card_y0 + 196)], fill=c_fg, width=1)

    # 6. Digital Clock: Perfectly Centered at Bottom of Card
    f_clock = get_font("bold", 46)
    f_ampm = get_font("bold", 18)
    cw, ch = text_dims(draw, time_str, f_clock)
    aw, ah = text_dims(draw, ampm_str, f_ampm)

    clock_block_w = cw + (8 + aw if ampm_str else 0)
    clock_start_x = card_cx - clock_block_w // 2

    draw.text((clock_start_x, card_y0 + 222), time_str, font=f_clock, fill=c_fg)
    if ampm_str:
        draw.text((clock_start_x + cw + 8, card_y0 + 238), ampm_str, font=f_ampm, fill=c_fg)

    # =========================================================================
    # SECTION 3: HOURLY TEMPERATURE GRAPH (Clean, Airy, Uncluttered)
    # =========================================================================
    g_x0, g_y0 = 262, 170
    g_w, g_h = SCREEN_WIDTH - g_x0 - 16, 298
    g_x1, g_y1 = g_x0 + g_w, g_y0 + g_h
    g_cx = g_x0 + g_w // 2

    draw.rounded_rectangle([g_x0, g_y0, g_x1, g_y1], radius=14, fill=c_bg, outline=c_fg, width=2)

    # Title: Centered at top of graph card
    f_ghdr = get_font("bold", 15)
    draw_centered_text(draw, g_cx, g_y0 + 14, "24-HOUR FORECAST", f_ghdr, c_fg)

    plot_left = g_x0 + 36
    plot_right = g_x1 - 36
    plot_top = g_y0 + 64
    plot_bottom = g_y1 - 58
    plot_w = plot_right - plot_left
    plot_h = plot_bottom - plot_top

    if len(hourly_entries) >= 4:
        temps = [t for _, t, _ in hourly_entries]
        min_t, max_t = min(temps), max(temps)
        t_range = max_t - min_t if max_t != min_t else 2

        t_pad = max(2.0, t_range * 0.25)
        plot_min_t = min_t - t_pad
        plot_max_t = max_t + t_pad
        effective_range = plot_max_t - plot_min_t

        n_pts = len(hourly_entries)
        xs, ys = [], []
        for i in range(n_pts):
            px = plot_left + int(i * (plot_w / (n_pts - 1)))
            py = int(plot_bottom - ((temps[i] - plot_min_t) / effective_range) * plot_h)
            xs.append(px)
            ys.append(py)

        # Subtle Horizontal Reference Gridlines
        for grid_val in (min_t, max_t):
            gy = int(plot_bottom - ((grid_val - plot_min_t) / effective_range) * plot_h)
            dash_len = 6
            gap_len = 5
            x_curr = plot_left - 10
            while x_curr < plot_right + 10:
                draw.line([(x_curr, gy), (min(x_curr + dash_len, plot_right + 10), gy)], fill=c_grid, width=1)
                x_curr += dash_len + gap_len

        # Smooth Cubic Spline Line (Crisp, clean 3px stroke - NO CLUTTERED SHADING)
        try:
            a, b, c, d, h = cubic_spline_coeffs(xs, ys)
            x_fine = np.linspace(xs[0], xs[-1], 250)
            y_fine = [eval_spline(a, b, c, d, h, xs, xi) for xi in x_fine]

            for k in range(len(x_fine) - 1):
                draw.line([(x_fine[k], y_fine[k]), (x_fine[k + 1], y_fine[k + 1])], fill=c_fg, width=3)
        except Exception:
            for k in range(len(xs) - 1):
                draw.line([(xs[k], ys[k]), (xs[k + 1], ys[k + 1])], fill=c_fg, width=3)

        # Baseline axis
        draw.line([(plot_left - 10, plot_bottom), (plot_right + 10, plot_bottom)], fill=c_grid, width=1)

        f_temp_lbl = get_font("bold", 18)
        f_hour_lbl = get_font("bold", 15)

        for i, (item_dt, t_val, _) in enumerate(hourly_entries):
            px, py = xs[i], ys[i]

            # Temperature Label: Perfectly Centered on node x
            t_str = f"{round(t_val)}{DEG}"
            draw_centered_text(draw, px, py - 28, t_str, f_temp_lbl, c_fg)

            # Node (Crisp circle with white center)
            r = 5
            draw.ellipse([px - r, py - r, px + r, py + r], fill=c_fg)
            draw.ellipse([px - r + 2, py - r + 2, px + r - 2, py + r - 2], fill=c_bg)

            # Vertical guide tick line down to baseline
            draw.line([(px, py + r + 2), (px, plot_bottom)], fill=c_grid, width=1)

            # Hour label: Perfectly Centered on node x
            if i == 0:
                h_str = "NOW"
            else:
                if use_24h:
                    h_str = item_dt.strftime("%H:%M")
                else:
                    h_str = item_dt.strftime("%I %p").lstrip("0")

            draw_centered_text(draw, px, plot_bottom + 12, h_str, f_hour_lbl, c_fg)

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
    img.save("/home/user/G4Cast/preview_clean.png")
    print("Preview image generated at /home/user/G4Cast/preview_clean.png")

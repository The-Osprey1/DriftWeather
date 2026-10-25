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
BULLET = "\u2022"

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

def load_weather_icon(icon_code, size=(72, 72), dark_mode=False, pic_dir="/home/user/G4Cast/pic"):
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

    # SOLID HIGH CONTRAST COLORS: Pure black and white for maximum e-ink legibility
    c_bg = 0 if dark_mode else 255
    c_fg = 255 if dark_mode else 0
    c_line = 180 if dark_mode else 80
    c_grid = 100 if dark_mode else 190

    img = Image.new("L", (SCREEN_WIDTH, SCREEN_HEIGHT), c_bg)
    draw = ImageDraw.Draw(img)

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
    date_str = local_dt.strftime("%a, %b %d").upper()

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
            daily_buckets[day_key] = {"dt": item_dt, "temps": [], "icons": [], "rain": 0}
        daily_buckets[day_key]["temps"].append(t_val)
        daily_buckets[day_key]["icons"].append(item["weather"][0]["icon"])

    sorted_days = sorted(daily_buckets.keys())[:5]
    days_data = []
    for d_k in sorted_days:
        b = daily_buckets[d_k]
        day_icons = [ic for ic in b["icons"] if ic.endswith("d")]
        if day_icons:
            icon_pick = max(set(day_icons), key=day_icons.count)
        else:
            icon_pick = max(set(b["icons"]), key=b["icons"].count).replace("n", "d")

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
    # SECTION 1: TOP 5-DAY FORECAST BAR (Height: 155px) - BOLD & HIGH CONTRAST
    # =========================================================================
    num_days = len(days_data)
    if num_days > 0:
        day_col_w = (SCREEN_WIDTH - 24) // num_days
        for i, d in enumerate(days_data):
            cx = 12 + i * day_col_w + day_col_w // 2

            # Day label: BOLD 18pt
            f_day = get_font("bold", 18)
            w, _ = text_dims(draw, d["name"], f_day)
            draw.text((cx - w // 2, 12), d["name"], font=f_day, fill=c_fg)

            # Weather Icon
            icon_img = load_weather_icon(d["icon"], size=(66, 66), dark_mode=dark_mode)
            img.paste(icon_img, (cx - 33, 38))

            # High / Low: BOLD & LARGER
            f_high = get_font("bold", 24)
            f_low = get_font("semibold", 20)
            f_sep = get_font("bold", 18)

            high_str = f"{d['high']}{DEG}"
            low_str = f"{d['low']}{DEG}"

            w_h, _ = text_dims(draw, high_str, f_high)
            w_sep, _ = text_dims(draw, "/", f_sep)
            w_l, _ = text_dims(draw, low_str, f_low)
            total_w = w_h + 6 + w_sep + 6 + w_l

            start_x = cx - total_w // 2
            draw.text((start_x, 112), high_str, font=f_high, fill=c_fg)
            draw.text((start_x + w_h + 6, 114), "/", font=f_sep, fill=c_fg)
            draw.text((start_x + w_h + 6 + w_sep + 6, 114), low_str, font=f_low, fill=c_fg)

            if i < num_days - 1:
                div_x = 12 + (i + 1) * day_col_w
                draw.line([(div_x, 16), (div_x, 144)], fill=c_line, width=1)

    # Main Horizontal Divider
    draw.line([(12, 156), (SCREEN_WIDTH - 12, 156)], fill=c_fg, width=2)

    # =========================================================================
    # SECTION 2: LEFT HERO CARD (Width: 224px, Height: 302px) - LARGE & BOLD
    # =========================================================================
    card_x0, card_y0 = 12, 168
    card_w, card_h = 224, 302
    card_x1, card_y1 = card_x0 + card_w, card_y0 + card_h

    # Strong outline
    draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=14, fill=c_bg, outline=c_fg, width=3)

    # City: BOLD 24pt
    f_city = get_font("bold", 24)
    draw.text((card_x0 + 16, card_y0 + 12), city_name, font=f_city, fill=c_fg)

    # Date: BOLD 14pt
    f_date = get_font("bold", 14)
    draw.text((card_x0 + 16, card_y0 + 40), date_str, font=f_date, fill=c_fg)

    # Hero Temp: BOLD 62pt & Large Icon
    f_hero_temp = get_font("bold", 62)
    temp_display = f"{cur_temp}{DEG}"

    hero_icon = load_weather_icon(cur_icon, size=(58, 58), dark_mode=dark_mode)
    img.paste(hero_icon, (card_x0 + 14, card_y0 + 64))
    draw.text((card_x0 + 82, card_y0 + 58), temp_display, font=f_hero_temp, fill=c_fg)

    # Condition & Feels Like: BOLD 18pt & 15pt
    f_desc = get_font("bold", 18)
    draw.text((card_x0 + 16, card_y0 + 128), cur_desc, font=f_desc, fill=c_fg)

    f_stats = get_font("semibold", 15)
    feels_str = f"Feels like {cur_feels}{DEG}"
    draw.text((card_x0 + 16, card_y0 + 152), feels_str, font=f_stats, fill=c_fg)

    # Secondary Stats: BOLD 14pt
    f_meta = get_font("bold", 14)
    meta_str = f"Humidity {humidity}%  |  {wind_str}"
    draw.text((card_x0 + 16, card_y0 + 176), meta_str, font=f_meta, fill=c_fg)

    # Clock Divider Line
    draw.line([(card_x0 + 12, card_y0 + 206), (card_x1 - 12, card_y0 + 206)], fill=c_fg, width=2)

    # Clock: BOLD 44pt
    f_clock = get_font("bold", 44)
    f_ampm = get_font("bold", 18)
    w_clock, _ = text_dims(draw, time_str, f_clock)
    w_ampm, _ = text_dims(draw, ampm_str, f_ampm)

    clock_total_w = w_clock + (6 + w_ampm if ampm_str else 0)
    clock_start_x = card_x0 + (card_w - clock_total_w) // 2

    draw.text((clock_start_x, card_y0 + 224), time_str, font=f_clock, fill=c_fg)
    if ampm_str:
        draw.text((clock_start_x + w_clock + 6, card_y0 + 238), ampm_str, font=f_ampm, fill=c_fg)

    # =========================================================================
    # SECTION 3: HOURLY TEMPERATURE GRAPH - THICK CURVE & LARGE LABELS
    # =========================================================================
    g_x0, g_y0 = 246, 168
    g_w, g_h = SCREEN_WIDTH - g_x0 - 12, 302
    g_x1, g_y1 = g_x0 + g_w, g_y0 + g_h

    draw.rounded_rectangle([g_x0, g_y0, g_x1, g_y1], radius=14, fill=c_bg, outline=c_fg, width=2)

    # Title: BOLD 15pt
    f_ghdr = get_font("bold", 15)
    draw.text((g_x0 + 18, g_y0 + 14), "24-HOUR FORECAST", font=f_ghdr, fill=c_fg)

    plot_left = g_x0 + 36
    plot_right = g_x1 - 36
    plot_top = g_y0 + 64
    plot_bottom = g_y1 - 60
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
        xs = [plot_left + int(i * (plot_w / (n_pts - 1))) for i in range(n_pts)]
        ys = [int(plot_bottom - ((t - plot_min_t) / effective_range) * plot_h) for t in temps]

        for grid_val in (min_t, max_t):
            gy = int(plot_bottom - ((grid_val - plot_min_t) / effective_range) * plot_h)
            dash_len = 6
            gap_len = 5
            x_curr = plot_left - 10
            while x_curr < plot_right + 10:
                draw.line([(x_curr, gy), (min(x_curr + dash_len, plot_right + 10), gy)], fill=c_grid, width=1)
                x_curr += dash_len + gap_len

        # Thick Cubic Spline Curve (4px)
        try:
            a, b, c, d, h = cubic_spline_coeffs(xs, ys)
            x_fine = np.linspace(xs[0], xs[-1], 250)
            y_fine = [eval_spline(a, b, c, d, h, xs, xi) for xi in x_fine]

            for k in range(len(x_fine) - 1):
                draw.line([(x_fine[k], y_fine[k]), (x_fine[k + 1], y_fine[k + 1])], fill=c_fg, width=4)
        except Exception:
            for k in range(len(xs) - 1):
                draw.line([(xs[k], ys[k]), (xs[k + 1], ys[k + 1])], fill=c_fg, width=4)

        f_temp_lbl = get_font("bold", 18)
        f_hour_lbl = get_font("bold", 15)

        for i, (item_dt, t_val, rain_val) in enumerate(hourly_entries):
            px, py = xs[i], ys[i]

            # Temperature Label with DEG
            t_str = f"{round(t_val)}{DEG}"
            tw, th = text_dims(draw, t_str, f_temp_lbl)
            draw.text((px - tw // 2, py - th - 12), t_str, font=f_temp_lbl, fill=c_fg)

            # Solid prominent node
            r = 6
            draw.ellipse([px - r, py - r, px + r, py + r], fill=c_fg)
            draw.ellipse([px - r + 2, py - r + 2, px + r - 2, py + r - 2], fill=c_bg)

            # Guide line down
            draw.line([(px, py + r + 2), (px, plot_bottom + 8)], fill=c_grid, width=1)

            # Hour label
            if i == 0:
                h_str = "NOW"
            else:
                if use_24h:
                    h_str = item_dt.strftime("%H:%M")
                else:
                    h_str = item_dt.strftime("%I %p").lstrip("0")

            hw, _ = text_dims(draw, h_str, f_hour_lbl)
            draw.text((px - hw // 2, plot_bottom + 14), h_str, font=f_hour_lbl, fill=c_fg)

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
    img.save("/home/user/G4Cast/preview_readable.png")
    print("Preview image generated at /home/user/G4Cast/preview_readable.png")

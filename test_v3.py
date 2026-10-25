# -*- coding: utf-8 -*-
import os
import sys
import json
import math
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

def c_to_f(c):
    return round(c * 9.0 / 5.0 + 32)

def mm_to_in(mm):
    return mm / 25.4

# Catmull-Rom Spline
def catmull_rom_spline(control_points, num_points_per_segment=20):
    if len(control_points) < 2:
        return control_points
    pts = [control_points[0]] + list(control_points) + [control_points[-1]]
    curve = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for t_step in range(num_points_per_segment):
            t = t_step / float(num_points_per_segment)
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            curve.append((round(x, 1), round(y, 1)))
    curve.append(control_points[-1])
    return curve

def create_stipple_pattern(width, height, dark_mode=False):
    pattern = Image.new("L", (width, height), 0 if dark_mode else 255)
    p_draw = ImageDraw.Draw(pattern)
    dot_color = 255 if dark_mode else 0
    # Clean 1 dot every 3x3 grid (subtle, crisp paper-like texture)
    for y in range(0, height, 4):
        for x in range(0, width, 4):
            if (x // 4 + y // 4) % 2 == 0:
                p_draw.point((x, y), fill=dot_color)
    return pattern

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
    c_line = 180 if dark_mode else 80
    c_grid = 100 if dark_mode else 190

    img = Image.new("L", (SCREEN_WIDTH, SCREEN_HEIGHT), c_bg)
    draw = ImageDraw.Draw(img)

    # Weather extraction
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

    # Sunrise & Sunset
    sr_ts = current_data.get("sys", {}).get("sunrise", 0)
    ss_ts = current_data.get("sys", {}).get("sunset", 0)
    sr_dt = datetime.fromtimestamp(sr_ts, timezone.utc) + timedelta(seconds=tz_offset)
    ss_dt = datetime.fromtimestamp(ss_ts, timezone.utc) + timedelta(seconds=tz_offset)

    if use_24h:
        time_str = local_dt.strftime("%H:%M")
        ampm_str = ""
        sr_str = sr_dt.strftime("%H:%M")
        ss_str = ss_dt.strftime("%H:%M")
    else:
        time_str = local_dt.strftime("%I:%M").lstrip("0")
        ampm_str = local_dt.strftime("%p")
        sr_str = sr_dt.strftime("%I:%M %p").lstrip("0")
        ss_str = ss_dt.strftime("%I:%M %p").lstrip("0")
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
    # SECTION 1: TOP 5-DAY FORECAST BAR (Height: 155px) WITH TODAY BADGE
    # =========================================================================
    num_days = len(days_data)
    if num_days > 0:
        day_col_w = (SCREEN_WIDTH - 24) // num_days
        for i, d in enumerate(days_data):
            cx = 12 + i * day_col_w + day_col_w // 2

            f_day = get_font("bold", 17)
            w, h = text_dims(draw, d["name"], f_day)

            # Highlighting TODAY with an inverted badge
            if d["is_today"]:
                badge_w = w + 16
                badge_h = h + 8
                draw.rounded_rectangle([cx - badge_w // 2, 8, cx + badge_w // 2, 8 + badge_h], radius=6, fill=c_fg)
                draw.text((cx - w // 2, 12), d["name"], font=f_day, fill=c_bg)
            else:
                draw.text((cx - w // 2, 12), d["name"], font=f_day, fill=c_fg)

            # Weather Icon
            icon_img = load_weather_icon(d["icon"], size=(64, 64), dark_mode=dark_mode)
            img.paste(icon_img, (cx - 32, 38))

            # High / Low
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
    # SECTION 2: LEFT HERO CARD (Width: 236px, Height: 304px) WITH PILL & SUNRISE
    # =========================================================================
    card_x0, card_y0 = 12, 168
    card_w, card_h = 236, 302
    card_x1, card_y1 = card_x0 + card_w, card_y0 + card_h

    draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=14, fill=c_bg, outline=c_fg, width=3)

    # City & Date
    f_city = get_font("bold", 24)
    draw.text((card_x0 + 16, card_y0 + 12), city_name, font=f_city, fill=c_fg)

    f_date = get_font("bold", 14)
    draw.text((card_x0 + 16, card_y0 + 40), date_str, font=f_date, fill=c_fg)

    # Hero Temp & Icon
    f_hero_temp = get_font("bold", 60)
    temp_display = f"{cur_temp}{DEG}"
    hero_icon = load_weather_icon(cur_icon, size=(58, 58), dark_mode=dark_mode)
    img.paste(hero_icon, (card_x0 + 14, card_y0 + 64))
    draw.text((card_x0 + 82, card_y0 + 58), temp_display, font=f_hero_temp, fill=c_fg)

    # Segmented High / Low Capsule Pill Badge: [ ? 95? | ? 64? ]
    f_pill = get_font("bold", 15)
    pill_x, pill_y = card_x0 + 16, card_y0 + 126
    pill_h = 26
    half_w = 48
    pill_r = 13

    # Left half (solid inverted with white text)
    draw.rounded_rectangle([pill_x, pill_y, pill_x + half_w, pill_y + pill_h], radius=pill_r, fill=c_fg)
    draw.rectangle([pill_x + half_w - pill_r, pill_y, pill_x + half_w, pill_y + pill_h], fill=c_fg)
    h_pill_txt = f"\u25b2 {today_high}{DEG}"
    tw, th = text_dims(draw, h_pill_txt, f_pill)
    draw.text((pill_x + (half_w - tw)//2, pill_y + 4), h_pill_txt, font=f_pill, fill=c_bg)

    # Right half (outline with black text)
    draw.rounded_rectangle([pill_x + half_w, pill_y, pill_x + half_w*2, pill_y + pill_h], radius=pill_r, fill=c_bg, outline=c_fg, width=2)
    draw.rectangle([pill_x + half_w, pill_y, pill_x + half_w + pill_r, pill_y + pill_h], fill=c_bg)
    draw.line([(pill_x + half_w, pill_y), (pill_x + half_w + pill_r, pill_y)], fill=c_fg, width=2)
    draw.line([(pill_x + half_w, pill_y + pill_h), (pill_x + half_w + pill_r, pill_y + pill_h)], fill=c_fg, width=2)
    l_pill_txt = f"\u25bc {today_low}{DEG}"
    tw2, th2 = text_dims(draw, l_pill_txt, f_pill)
    draw.text((pill_x + half_w + (half_w - tw2)//2, pill_y + 4), l_pill_txt, font=f_pill, fill=c_fg)

    # Condition & Feels Like
    f_desc = get_font("bold", 16)
    draw.text((card_x0 + 125, card_y0 + 128), cur_desc, font=f_desc, fill=c_fg)

    # Humidity & Wind
    f_meta = get_font("bold", 14)
    meta_str = f"Humidity {humidity}%  |  {wind_str}"
    draw.text((card_x0 + 16, card_y0 + 160), meta_str, font=f_meta, fill=c_fg)

    # Sunrise & Sunset display
    f_sun = get_font("bold", 13)
    sun_str = f"\u2191 {sr_str}   \u2193 {ss_str}"
    draw.text((card_x0 + 16, card_y0 + 182), sun_str, font=f_sun, fill=c_fg)

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
    # SECTION 3: 24-HOUR TEMPERATURE GRAPH WITH HALFTONE SHADING
    # =========================================================================
    g_x0, g_y0 = 258, 168
    g_w, g_h = SCREEN_WIDTH - g_x0 - 12, 302
    g_x1, g_y1 = g_x0 + g_w, g_y0 + g_h

    draw.rounded_rectangle([g_x0, g_y0, g_x1, g_y1], radius=14, fill=c_bg, outline=c_fg, width=2)

    # Title
    f_ghdr = get_font("bold", 15)
    draw.text((g_x0 + 18, g_y0 + 14), "24-HOUR FORECAST", font=f_ghdr, fill=c_fg)

    plot_left = g_x0 + 36
    plot_right = g_x1 - 36
    plot_top = g_y0 + 60
    plot_bottom = g_y1 - 56
    plot_w = plot_right - plot_left
    plot_h = plot_bottom - plot_top

    if len(hourly_entries) >= 4:
        temps = [t for _, t, _, _ in hourly_entries]
        min_t, max_t = min(temps), max(temps)
        t_range = max_t - min_t if max_t != min_t else 2

        t_pad = max(2.0, t_range * 0.25)
        plot_min_t = min_t - t_pad
        plot_max_t = max_t + t_pad
        effective_range = plot_max_t - plot_min_t

        n_pts = len(hourly_entries)
        ctrl_pts = []
        xs, ys = [], []
        for i in range(n_pts):
            px = plot_left + int(i * (plot_w / (n_pts - 1)))
            py = int(plot_bottom - ((temps[i] - plot_min_t) / effective_range) * plot_h)
            ctrl_pts.append((px, py))
            xs.append(px)
            ys.append(py)

        # Generate smooth Catmull-Rom spline points
        spline_pts = catmull_rom_spline(ctrl_pts, num_points_per_segment=16)

        # 1-Bit Halftone Shaded Area Under the Spline Curve!
        poly_pts = [(spline_pts[0][0], plot_bottom)] + spline_pts + [(spline_pts[-1][0], plot_bottom)]
        mask = Image.new("L", (SCREEN_WIDTH, SCREEN_HEIGHT), 0)
        ImageDraw.Draw(mask).polygon(poly_pts, fill=255)
        stipple_pat = create_stipple_pattern(SCREEN_WIDTH, SCREEN_HEIGHT, dark_mode=dark_mode)
        img.paste(stipple_pat, (0, 0), mask=mask)

        # Horizontal Gridlines (Min & Max reference)
        for grid_val in (min_t, max_t):
            gy = int(plot_bottom - ((grid_val - plot_min_t) / effective_range) * plot_h)
            dash_len = 6
            gap_len = 5
            x_curr = plot_left - 10
            while x_curr < plot_right + 10:
                draw.line([(x_curr, gy), (min(x_curr + dash_len, plot_right + 10), gy)], fill=c_grid, width=1)
                x_curr += dash_len + gap_len

        # Thick Spline Curve Stroke (4px)
        for k in range(len(spline_pts) - 1):
            draw.line([(spline_pts[k][0], spline_pts[k][1]), (spline_pts[k+1][0], spline_pts[k+1][1])], fill=c_fg, width=4)

        # Baseline
        draw.line([(plot_left - 10, plot_bottom), (plot_right + 10, plot_bottom)], fill=c_grid, width=1)

        f_temp_lbl = get_font("bold", 18)
        f_hour_lbl = get_font("bold", 15)
        f_pop_lbl = get_font("bold", 11)

        for i, (item_dt, t_val, rain_val, pop_val) in enumerate(hourly_entries):
            px, py = xs[i], ys[i]

            # Temperature Label with DEG
            t_str = f"{round(t_val)}{DEG}"
            tw, th = text_dims(draw, t_str, f_temp_lbl)
            draw.text((px - tw // 2, py - th - 12), t_str, font=f_temp_lbl, fill=c_fg)

            # Solid prominent node (outer fg, inner bg)
            r = 6
            draw.ellipse([px - r, py - r, px + r, py + r], fill=c_fg)
            draw.ellipse([px - r + 2, py - r + 2, px + r - 2, py + r - 2], fill=c_bg)

            # Guide line down
            draw.line([(px, py + r + 2), (px, plot_bottom + 6)], fill=c_grid, width=1)

            # Hour label
            if i == 0:
                h_str = "NOW"
            else:
                if use_24h:
                    h_str = item_dt.strftime("%H:%M")
                else:
                    h_str = item_dt.strftime("%I %p").lstrip("0")

            hw, _ = text_dims(draw, h_str, f_hour_lbl)
            draw.text((px - hw // 2, plot_bottom + 12), h_str, font=f_hour_lbl, fill=c_fg)

            # Rain Chance % if > 0
            if pop_val and pop_val > 0.05:
                pop_pct = f"{int(pop_val * 100)}%"
                pw, _ = text_dims(draw, pop_pct, f_pop_lbl)
                draw.text((px - pw // 2, plot_bottom + 32), pop_pct, font=f_pop_lbl, fill=c_fg)

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
    img.save("/home/user/G4Cast/preview_v3.png")
    print("Preview image generated at /home/user/G4Cast/preview_v3.png")

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

# Draw a crisp 1-bit teardrop icon
def draw_droplet(draw, cx, cy, size=10, fill=0):
    r = size // 2
    draw.ellipse([cx - r, cy - r // 2, cx + r, cy + r + r // 2], fill=fill)
    draw.polygon([(cx - r + 1, cy), (cx, cy - size), (cx + r - 1, cy)], fill=fill)

def render_demo(dark_mode=False):
    c_bg = 0 if dark_mode else 255
    c_fg = 255 if dark_mode else 0
    c_line = 180 if dark_mode else 90
    c_grid = 110 if dark_mode else 190
    c_bar = 200 if dark_mode else 160

    img = Image.new("L", (SCREEN_WIDTH, SCREEN_HEIGHT), c_bg)
    draw = ImageDraw.Draw(img)

    # 3-DIGIT DEMO: 104 deg F in Eastvale!
    cur_temp = 104
    today_high = 108
    today_low = 78
    cur_desc = "Hot & Sunny"
    humidity = 32
    wind_str = "8 mph"
    time_str = "3:45"
    ampm_str = "PM"
    date_str = "Saturday, Jul 18"
    city_name = "Eastvale"

    days_data = [
        {"name": "TODAY", "high": 108, "low": 78, "icon": "01d"},
        {"name": "SUN", "high": 105, "low": 76, "icon": "01d"},
        {"name": "MON", "high": 102, "low": 75, "icon": "02d"},
        {"name": "TUE", "high": 96, "low": 72, "icon": "10d"}, # rain!
        {"name": "WED", "high": 92, "low": 70, "icon": "03d"},
    ]

    # TOP 5-DAY BAR (Adjusted for 3 digits: 20pt font)
    bar_left = 16
    bar_right = SCREEN_WIDTH - 16
    col_w = (bar_right - bar_left) // 5

    for i, d in enumerate(days_data):
        cx = bar_left + i * col_w + col_w // 2
        f_day = get_font("bold", 18)
        draw_centered_text(draw, cx, 14, d["name"], f_day, c_fg)

        icon_img = load_weather_icon(d["icon"], size=(64, 64))
        img.paste(icon_img, (cx - 32, 42))

        # 3-digit temps fit comfortably at 20pt bold
        f_hl = get_font("bold", 20)
        hl_str = f"{d['high']}{DEG}  {d['low']}{DEG}"
        draw_centered_text(draw, cx, 114, hl_str, f_hl, c_fg)

        if i < 4:
            div_x = bar_left + (i + 1) * col_w
            draw.line([(div_x, 18), (div_x, 142)], fill=c_line, width=1)

    draw.line([(16, 156), (SCREEN_WIDTH - 16, 156)], fill=c_fg, width=2)

    # LEFT HERO CARD (Width: 230px)
    card_x0, card_y0 = 16, 170
    card_w, card_h = 230, 298
    card_x1, card_y1 = card_x0 + card_w, card_y0 + card_h
    card_cx = card_x0 + card_w // 2

    draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=14, fill=c_bg, outline=c_fg, width=2)
    draw_centered_text(draw, card_cx, card_y0 + 14, city_name, get_font("bold", 24), c_fg)
    draw_centered_text(draw, card_cx, card_y0 + 44, date_str, get_font("semibold", 13), c_fg)

    # DYNAMIC FONT SCALING FOR 3-DIGIT HERO TEMP:
    # If 3 digits (>= 100), scale font slightly from 62pt to 54pt so it fits with generous margins!
    temp_str = f"{cur_temp}{DEG}"
    hero_font_size = 52 if cur_temp >= 100 else 62
    f_hero_temp = get_font("bold", hero_font_size)
    tw, th = text_dims(draw, temp_str, f_hero_temp)

    hero_icon = load_weather_icon("01d", size=(50, 50))
    block_w = 50 + 8 + tw
    block_start_x = card_cx - block_w // 2
    img.paste(hero_icon, (block_start_x, card_y0 + 68))
    draw.text((block_start_x + 50 + 8, card_y0 + 64), temp_str, font=f_hero_temp, fill=c_fg)

    sub_str = f"{cur_desc}  \u2022  H: {today_high}{DEG}  L: {today_low}{DEG}"
    draw_centered_text(draw, card_cx, card_y0 + 134, sub_str, get_font("bold", 15), c_fg)

    meta_str = f"Humidity {humidity}%   Wind {wind_str}"
    draw_centered_text(draw, card_cx, card_y0 + 160, meta_str, get_font("semibold", 13), c_fg)

    draw.line([(card_x0 + 16, card_y0 + 196), (card_x1 - 16, card_y0 + 196)], fill=c_fg, width=1)

    f_clock = get_font("bold", 46)
    f_ampm = get_font("bold", 18)
    cw, _ = text_dims(draw, time_str, f_clock)
    aw, _ = text_dims(draw, ampm_str, f_ampm)
    clock_block_w = cw + (8 + aw if ampm_str else 0)
    clock_start_x = card_cx - clock_block_w // 2
    draw.text((clock_start_x, card_y0 + 222), time_str, font=f_clock, fill=c_fg)
    draw.text((clock_start_x + cw + 8, card_y0 + 238), ampm_str, font=f_ampm, fill=c_fg)

    # RIGHT 24-HOUR GRAPH WITH PRECIPITATION TIMELINE
    g_x0, g_y0 = 262, 170
    g_w, g_h = SCREEN_WIDTH - g_x0 - 16, 298
    g_x1, g_y1 = g_x0 + g_w, g_y0 + g_h
    g_cx = g_x0 + g_w // 2

    draw.rounded_rectangle([g_x0, g_y0, g_x1, g_y1], radius=14, fill=c_bg, outline=c_fg, width=2)
    draw_centered_text(draw, g_cx, g_y0 + 14, "24-HOUR FORECAST", get_font("bold", 15), c_fg)

    plot_left = g_x0 + 36
    plot_right = g_x1 - 36
    plot_top = g_y0 + 64
    plot_bottom = g_y1 - 62
    plot_w = plot_right - plot_left
    plot_h = plot_bottom - plot_top

    # Hourly mock data: High summer temps + evening summer rainstorm (70% pop at 9PM & 12AM)
    hourly_demo = [
        ("NOW", 104, 0.0, 0),
        ("6 PM", 102, 0.0, 0),
        ("9 PM", 91, 2.5, 75),  # 75% rain chance, 2.5mm rain!
        ("12 AM", 82, 4.0, 85), # 85% rain chance, 4.0mm rain!
        ("3 AM", 79, 0.5, 30),  # 30% lingering rain
        ("6 AM", 78, 0.0, 0),
        ("9 AM", 88, 0.0, 0),
        ("12 PM", 99, 0.0, 0)
    ]

    temps = [t for _, t, _, _ in hourly_demo]
    min_t, max_t = min(temps), max(temps)
    t_range = max_t - min_t if max_t != min_t else 2
    t_pad = max(2.0, t_range * 0.25)
    plot_min_t = min_t - t_pad
    plot_max_t = max_t + t_pad
    effective_range = plot_max_t - plot_min_t

    n_pts = len(hourly_demo)
    xs, ys = [], []
    for i in range(n_pts):
        px = plot_left + int(i * (plot_w / (n_pts - 1)))
        py = int(plot_bottom - ((temps[i] - plot_min_t) / effective_range) * plot_h)
        xs.append(px)
        ys.append(py)

    # PRECIPITATION BARS & RAIN ICONS ALONG BOTTOM TIMELINE
    # If rain amount > 0, draw a clean precipitation column from baseline up
    for i in range(n_pts - 1):
        rain_mm = hourly_demo[i][2]
        if rain_mm > 0.1:
            bar_x0 = xs[i] - 12
            bar_x1 = xs[i] + 12
            bar_height = min(28, int(rain_mm * 6)) # scale to max 28px
            bar_y0 = plot_bottom - bar_height
            bar_y1 = plot_bottom
            # Clean shaded precipitation bar
            draw.rectangle([bar_x0, bar_y0, bar_x1, bar_y1], fill=c_bar)
            draw.rectangle([bar_x0, bar_y0, bar_x1, bar_y1], outline=c_fg, width=1)

    # Gridlines
    for grid_val in (min_t, max_t):
        gy = int(plot_bottom - ((grid_val - plot_min_t) / effective_range) * plot_h)
        dash_len, gap_len = 6, 5
        x_curr = plot_left - 10
        while x_curr < plot_right + 10:
            draw.line([(x_curr, gy), (min(x_curr + dash_len, plot_right + 10), gy)], fill=c_grid, width=1)
            x_curr += dash_len + gap_len

    # Spline Curve
    try:
        a, b, c, d, h = cubic_spline_coeffs(xs, ys)
        x_fine = np.linspace(xs[0], xs[-1], 250)
        y_fine = [eval_spline(a, b, c, d, h, xs, xi) for xi in x_fine]
        for k in range(len(x_fine) - 1):
            draw.line([(x_fine[k], y_fine[k]), (x_fine[k + 1], y_fine[k + 1])], fill=c_fg, width=3)
    except Exception:
        for k in range(len(xs) - 1):
            draw.line([(xs[k], ys[k]), (xs[k + 1], ys[k + 1])], fill=c_fg, width=3)

    # Baseline
    draw.line([(plot_left - 10, plot_bottom), (plot_right + 10, plot_bottom)], fill=c_grid, width=1)

    # Labels (17pt for 3-digit temps fits perfectly)
    f_temp_lbl = get_font("bold", 17)
    f_hour_lbl = get_font("bold", 14)
    f_pop_lbl = get_font("bold", 12)

    for i, (h_lbl, t_val, rain_mm, pop_val) in enumerate(hourly_demo):
        px, py = xs[i], ys[i]

        # Temp Label (e.g. 104 deg)
        draw_centered_text(draw, px, py - 26, f"{t_val}{DEG}", f_temp_lbl, c_fg)

        # Node
        r = 5
        draw.ellipse([px - r, py - r, px + r, py + r], fill=c_fg)
        draw.ellipse([px - r + 2, py - r + 2, px + r - 2, py + r - 2], fill=c_bg)

        # Vertical guide tick line
        draw.line([(px, py + r + 2), (px, plot_bottom)], fill=c_grid, width=1)

        # Hour label
        draw_centered_text(draw, px, plot_bottom + 8, h_lbl, f_hour_lbl, c_fg)

        # PRECIPITATION BADGE: If pop > 15%, draw cute teardrop + percentage under the hour
        if pop_val >= 15:
            # Draw droplet + text
            pop_txt = f"{pop_val}%"
            tw, _ = text_dims(draw, pop_txt, f_pop_lbl)
            drop_total_w = 8 + 4 + tw
            start_x = px - drop_total_w // 2
            draw_droplet(draw, start_x + 4, plot_bottom + 34, size=8, fill=c_fg)
            draw.text((start_x + 12, plot_bottom + 27), pop_txt, font=f_pop_lbl, fill=c_fg)

    return img

if __name__ == "__main__":
    img = render_demo(dark_mode=False)
    img.save("/home/user/G4Cast/preview_3digits_rain.png")
    print("Demo rendered to /home/user/G4Cast/preview_3digits_rain.png")

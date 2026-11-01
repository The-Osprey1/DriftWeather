#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Pixel-Perfect 800x480 Monochrome E-Paper Renderer
Renders high-contrast, mathematically balanced weather layout with cubic spline curves
and conditional subtle freshness indicators.
"""

import os
import io
import math
import logging
import threading
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont, ImageOps
from typing import Optional, Dict, Any, List, Tuple, Union

logger = logging.getLogger("G4Cast.Renderer")

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
DEG = "\u00b0"

try:
    from config.settings import normalize_layout_style, normalize_hero_size
except Exception:
    def normalize_layout_style(val) -> str:
        if val is not None:
            v = str(val).strip().lower()
            if v in ("widgets", "widget", "tiles", "option1", "1"):
                return "widgets"
            elif v in ("dualtone", "dual-tone", "dual_tone", "inverted", "option2", "2"):
                return "dualtone"
            elif v in ("minimalist", "minimal", "editorial", "option3", "3"):
                return "minimalist"
        return "classic"

    def normalize_hero_size(val) -> str:
        if val is not None:
            v = str(val).strip().lower()
            if v in ("large", "huge", "big", "glanceable"):
                return "large"
            elif v in ("compact", "small", "dense"):
                return "compact"
        return "standard"

def text_dims(draw: ImageDraw.Draw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), str(text), font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    return draw.textsize(str(text), font=font)

def draw_centered_text(draw: ImageDraw.Draw, cx: int, y: int, text: str, font: ImageFont.ImageFont, fill: int) -> Tuple[int, int]:
    w, h = text_dims(draw, text, font)
    draw.text((cx - w // 2, y), str(text), font=font, fill=fill)
    return w, h

def draw_dashed_line(draw: ImageDraw.Draw, x0: int, y0: int, x1: int, y1: int, dash: int = 3, gap: int = 3, fill: int = 0, width: int = 1):
    dx = x1 - x0
    dy = y1 - y0
    dist = int(np.hypot(dx, dy))
    if dist == 0:
        return
    vx = dx / dist
    vy = dy / dist
    curr = 0
    while curr < dist:
        seg_end = min(curr + dash, dist)
        draw.line(
            [(int(x0 + vx * curr), int(y0 + vy * curr)), (int(x0 + vx * seg_end), int(y0 + vy * seg_end))],
            fill=fill, width=width
        )
        curr += dash + gap

def to_sharp_1bit(img: Image.Image, threshold: Optional[int] = None, dark_mode: Optional[bool] = None) -> Image.Image:
    """
    Converts a grayscale image to a sharp 1-bit monochrome image with zero dithering.
    Automatically applies symmetrical thresholding:
      - Light mode (dark_mode=False): threshold = 150 (preserves stroke coverage >= 41.2%)
      - Dark mode (dark_mode=True):   threshold = 105 (255 - 150 = 105, restores stroke weight symmetry)
    If threshold and dark_mode are omitted, automatically infers background polarity from
    the canvas corner pixel (0 = black canvas -> 105, 255 = white canvas -> 150).
    """
    if threshold is None:
        if dark_mode is not None:
            threshold = 105 if dark_mode else 150
        else:
            l_img = img if img.mode == 'L' else img.convert('L')
            corner_val = l_img.getpixel((0, 0))
            threshold = 105 if corner_val < 128 else 150

    if img.mode != 'L':
        img = img.convert('L')
    table = [0 if i < threshold else 255 for i in range(256)]
    return img.point(table, mode='1')

def draw_droplet(draw: ImageDraw.Draw, cx: int, cy: int, size: int = 10, fill: int = 0):
    r = size // 2
    draw.ellipse([cx - r, cy - r // 2, cx + r, cy + r + r // 2], fill=fill)
    draw.polygon([(cx - r + 1, cy), (cx, cy - size), (cx + r - 1, cy)], fill=fill)

def get_moon_phase(dt: Optional[datetime] = None) -> Tuple[float, str]:
    if dt is None:
        dt = datetime.now(timezone.utc)
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    diff_sec = (dt - ref).total_seconds()
    synodic_days = 29.53058867
    phase = ((diff_sec / 86400.0) % synodic_days) / synodic_days

    if phase < 0.04 or phase >= 0.96:
        name = "New Moon"
    elif phase < 0.22:
        name = "Waxing Crescent"
    elif phase < 0.28:
        name = "First Quarter"
    elif phase < 0.46:
        name = "Waxing Gibbous"
    elif phase < 0.54:
        name = "Full Moon"
    elif phase < 0.72:
        name = "Waning Gibbous"
    elif phase < 0.78:
        name = "Third Quarter"
    else:
        name = "Waning Crescent"
    return phase, name

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

class WeatherRenderer:
    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            self.base_dir = Path(__file__).resolve().parent.parent
        else:
            self.base_dir = Path(base_dir)

        self.picdir = self.base_dir / "pic"
        self.font_dir = Path("/usr/share/fonts/opentype/inter")

        self.fonts = {
            "black": str(self.font_dir / "Inter-Black.otf"),
            "bold": str(self.font_dir / "Inter-Bold.otf"),
            "semibold": str(self.font_dir / "Inter-SemiBold.otf"),
            "medium": str(self.font_dir / "Inter-Medium.otf"),
            "regular": str(self.font_dir / "Inter-Regular.otf"),
            "fallback": str(self.picdir / "Font.ttc"),
            "dejavu": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        }

        self.current_image: Optional[Image.Image] = None

    def get_font(self, weight: str = "bold", size: int = 18) -> ImageFont.ImageFont:
        target = self.fonts.get(weight, self.fonts["bold"])
        candidates = [
            target,
            self.fonts.get("bold"),
            self.fonts.get("semibold"),
            self.fonts.get("medium"),
            self.fonts.get("dejavu"),
            self.fonts.get("fallback"),
            r"C:\Windows\Fonts\seguibl.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\segoeuisl.ttf",
            r"C:\Windows\Fonts\segoeui.ttf"
        ]
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def load_weather_icon(self, icon_code: str, size: Tuple[int, int] = (46, 46), dark_mode: Any = False) -> Image.Image:
        if isinstance(dark_mode, str):
            is_dark_mode = dark_mode.strip().lower() in ("on", "true", "yes", "1", "dark")
        elif isinstance(dark_mode, (int, float)):
            is_dark_mode = (dark_mode == 1)
        else:
            is_dark_mode = bool(dark_mode)

        filename = f"{icon_code}.png"
        path = self.picdir / filename
        if not path.exists():
            clean_code = icon_code.replace("n", "d")
            path = self.picdir / f"{clean_code}.png"
        if not path.exists():
            path = self.picdir / "01d.png"

        try:
            icon = Image.open(str(path)).convert("RGBA")
            icon = icon.resize(size, Image.Resampling.LANCZOS)
            bg = Image.new("L", size, 0 if is_dark_mode else 255)
            mask = icon.split()[3]
            gray_icon = icon.convert("L")
            if is_dark_mode:
                gray_icon = ImageOps.invert(gray_icon)
            bg.paste(gray_icon, (0, 0), mask)
            return bg
        except Exception as e:
            logger.debug("Icon load error for %s: %s", icon_code, e)
            return Image.new("L", size, 0 if is_dark_mode else 255)

    def draw_lunar_phase(self, draw: ImageDraw.Draw, cx: int, cy: int, radius: int = 6,
                         phase: float = 0.5, fill: int = 0, bg: int = 255):
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=fill, width=1)
        r = radius
        if 0.48 <= phase <= 0.52:
            draw.ellipse([cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1], fill=fill)
            return
        if phase < 0.04 or phase > 0.96:
            return

        is_waxing = phase < 0.5
        illuminated_fraction = 1.0 - 2.0 * abs(phase - 0.5)

        for y in range(-r, r + 1):
            dx = int(math.sqrt(max(0, r * r - y * y)))
            if dx == 0:
                continue
            x_left = cx - dx
            x_right = cx + dx
            x_term = cx + int((2 * illuminated_fraction - 1) * dx)
            if is_waxing:
                x_start = min(x_term, x_right)
                x_end = x_right
            else:
                x_start = x_left
                x_end = max(x_term, x_left)
            if x_start < x_end:
                draw.line([(x_start, cy + y), (x_end, cy + y)], fill=fill, width=1)

    def draw_droplet_icon(self, draw: ImageDraw.Draw, cx: int, cy: int, r: float = 4.5, fill: int = 0):
        draw.ellipse([cx - r, cy - r * 0.3, cx + r, cy + r * 1.5], outline=fill, width=1)
        draw.polygon([(cx - r * 0.9, cy + r * 0.2), (cx, cy - r * 1.5), (cx + r * 0.9, cy + r * 0.2)], fill=fill)

    def draw_wind_icon(self, draw: ImageDraw.Draw, cx: int, cy: int, w: int = 15, fill: int = 0):
        draw.line([(cx - w // 2, cy - 3), (cx + w // 2 - 2, cy - 3)], fill=fill, width=1)
        draw.arc([cx + w // 2 - 5, cy - 6, cx + w // 2, cy], 270, 90, fill=fill, width=1)
        draw.line([(cx - w // 2 - 2, cy + 2), (cx + w // 2 - 5, cy + 2)], fill=fill, width=1)
        draw.arc([cx + w // 2 - 7, cy, cx + w // 2 - 2, cy + 5], 270, 90, fill=fill, width=1)

    def draw_sunrise_icon(self, draw: ImageDraw.Draw, cx: int, cy: int, r: int = 5, fill: int = 0):
        draw.arc([cx - r, cy - r, cx + r, cy + r], 180, 0, fill=fill, width=1)
        draw.line([(cx - r - 4, cy + 1), (cx + r + 4, cy + 1)], fill=fill, width=1)
        draw.line([(cx, cy - r - 4), (cx, cy - r - 1)], fill=fill, width=1)
        draw.line([(cx - 5, cy - 3), (cx - 7, cy - 5)], fill=fill, width=1)
        draw.line([(cx + 5, cy - 3), (cx + 7, cy - 5)], fill=fill, width=1)

    def draw_sunset_icon(self, draw: ImageDraw.Draw, cx: int, cy: int, r: int = 5, fill: int = 0):
        draw.arc([cx - r, cy - r, cx + r, cy + r], 180, 0, fill=fill, width=1)
        draw.line([(cx - r - 4, cy + 1), (cx + r + 4, cy + 1)], fill=fill, width=1)
        draw.line([(cx, cy - 1), (cx, cy + 2)], fill=fill, width=1)
        draw.polygon([(cx - 2, cy), (cx + 2, cy), (cx, cy + 4)], fill=fill)

    def _evaluate_solar_dark_mode(self, current_data: Optional[dict] = None) -> bool:
        """Helper to determine dark mode in auto mode based on current data timestamps."""
        sys_data = current_data.get("sys", {}) if current_data else {}
        sr_ts = sys_data.get("sunrise", 0)
        ss_ts = sys_data.get("sunset", 0)
        tz_offset = current_data.get("timezone", -25200) if current_data else -25200

        utc_now = datetime.now(timezone.utc)
        local_dt = utc_now + timedelta(seconds=tz_offset)
        curr_min = local_dt.hour * 60 + local_dt.minute

        if sr_ts and ss_ts:
            try:
                sr_dt = datetime.fromtimestamp(sr_ts, timezone.utc) + timedelta(seconds=tz_offset)
                ss_dt = datetime.fromtimestamp(ss_ts, timezone.utc) + timedelta(seconds=tz_offset)
                sr_min = sr_dt.hour * 60 + sr_dt.minute
                ss_min = ss_dt.hour * 60 + ss_dt.minute
                if sr_min <= ss_min:
                    return not (sr_min <= curr_min < ss_min)
                else:
                    return not (curr_min >= sr_min or curr_min < ss_min)
            except Exception:
                pass
        # Default fallback: daylight between 06:30 and 19:30
        return not (390 <= curr_min < 1170)

    def _prepare_data(self, forecast_data: dict, current_data: dict,
                      kcno_obs: Optional[dict] = None,
                      use_metric: bool = False,
                      display_name_override: str = "",
                      use_24h: bool = False) -> dict:
        cur_main = current_data.get("main", {})
        temp_k = cur_main.get("temp", 273.15)
        humidity = cur_main.get("humidity", 0)
        wind_speed = current_data.get("wind", {}).get("speed", 0)
        cur_weather = current_data.get("weather", [{}])[0]
        cur_icon = cur_weather.get("icon", "01d")
        cur_desc = cur_weather.get("main", "Clear").title()

        if kcno_obs:
            if kcno_obs.get("description"):
                cur_desc = kcno_obs["description"]
            if kcno_obs.get("icon"):
                cur_icon = kcno_obs["icon"]
            if kcno_obs.get("temp_c") is not None:
                temp_k = kcno_obs["temp_c"] + 273.15
            if kcno_obs.get("humidity") is not None:
                humidity = kcno_obs["humidity"]
            if kcno_obs.get("wind_kmh") is not None:
                wind_speed = kcno_obs["wind_kmh"] / 3.6

        if use_metric:
            cur_temp = round(temp_k - 273.15)
            wind_str = f"{round(wind_speed * 3.6)} km/h"
        else:
            cur_temp = round((temp_k - 273.15) * 9.0 / 5.0 + 32)
            wind_str = f"{round(wind_speed * 2.237)} mph"

        city_name = display_name_override if display_name_override else current_data.get("name", "Eastvale").split(",")[0]

        tz_offset = current_data.get("timezone", -25200)
        utc_now = datetime.now(timezone.utc)
        local_dt = utc_now + timedelta(seconds=tz_offset)

        if use_24h:
            time_str = local_dt.strftime("%H:%M")
            ampm_str = ""
        else:
            time_str = local_dt.strftime("%I:%M").lstrip("0")
            ampm_str = local_dt.strftime("%p")
        date_str = local_dt.strftime("%A, %b %d")

        daily_buckets = {}
        hourly_entries = []
        forecast_list = forecast_data.get("list", [])

        for item in forecast_list:
            dt_txt = item.get("dt_txt", "")
            try:
                item_dt = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S") + timedelta(seconds=tz_offset)
            except Exception:
                item_dt = local_dt
            day_key = item_dt.strftime("%Y-%m-%d")
            t_c = item.get("main", {}).get("temp", 273.15) - 273.15
            t_val = t_c if use_metric else round(t_c * 9.0 / 5.0 + 32)
            rain_val = item.get("rain", {}).get("3h", 0)
            raw_pop = item.get("pop", 0)
            pop_val = round(raw_pop * 100) if raw_pop <= 1.0 else round(raw_pop)

            if len(hourly_entries) < 8:
                hourly_entries.append((item_dt, t_val, rain_val, pop_val))

            if day_key not in daily_buckets:
                daily_buckets[day_key] = {"dt": item_dt, "temps": [], "icons": []}
            daily_buckets[day_key]["temps"].append(t_val)
            item_weather = item.get("weather", [{}])[0]
            daily_buckets[day_key]["icons"].append(item_weather.get("icon", "01d"))

        sorted_days = sorted(daily_buckets.keys())[:5]
        days_data = []
        today_high, today_low = cur_temp, cur_temp

        for i, d_k in enumerate(sorted_days):
            b = daily_buckets[d_k]
            day_icons = [ic for ic in b["icons"] if ic.endswith("d")]
            icon_pick = max(set(day_icons), key=day_icons.count) if day_icons else max(set(b["icons"]), key=b["icons"].count).replace("n", "d")
            h_val = round(max(b["temps"])) if b["temps"] else cur_temp
            l_val = round(min(b["temps"])) if b["temps"] else cur_temp
            if i == 0:
                day_name = "TODAY"
                today_high = max(cur_temp, h_val)
                today_low = min(cur_temp, l_val)
            else:
                day_name = b["dt"].strftime("%a").upper()

            days_data.append({
                "name": day_name,
                "high": h_val,
                "low": l_val,
                "icon": icon_pick,
                "dt": b["dt"]
            })

        sys_data = current_data.get("sys", {})
        sr_ts = sys_data.get("sunrise", 0)
        ss_ts = sys_data.get("sunset", 0)
        if sr_ts and ss_ts:
            sr_dt = datetime.fromtimestamp(sr_ts, timezone.utc) + timedelta(seconds=tz_offset)
            ss_dt = datetime.fromtimestamp(ss_ts, timezone.utc) + timedelta(seconds=tz_offset)
            sr_str = sr_dt.strftime("%I:%M %p").lstrip("0")
            ss_str = ss_dt.strftime("%I:%M %p").lstrip("0")
        else:
            sr_str = "6:32 AM"
            ss_str = "7:00 PM"

        moon_phase, _ = get_moon_phase(local_dt)

        return {
            "cur_temp": cur_temp,
            "cur_desc": cur_desc,
            "cur_icon": cur_icon,
            "humidity": humidity,
            "wind_str": wind_str,
            "city_name": city_name,
            "time_str": time_str,
            "ampm_str": ampm_str,
            "date_str": date_str,
            "local_dt": local_dt,
            "tz_offset": tz_offset,
            "days_data": days_data,
            "hourly_entries": hourly_entries,
            "today_high": today_high,
            "today_low": today_low,
            "sunrise_str": sr_str,
            "sunset_str": ss_str,
            "moon_phase": moon_phase,
            "use_metric": use_metric,
            "use_24h": use_24h
        }

    def _draw_aqi_badge(self, draw: ImageDraw.Draw, aqi_text: Any,
                        COLOR_FG: int, COLOR_BG: int,
                        box_coords: Tuple[int, int, int, int] = (676, 162, 764, 184)):
        if aqi_text is None or isinstance(aqi_text, bool):
            return
        if isinstance(aqi_text, (bytes, bytearray)):
            try:
                raw_str = aqi_text.decode("utf-8", errors="ignore")
            except Exception:
                raw_str = ""
        elif isinstance(aqi_text, (str, int, float)):
            raw_str = str(aqi_text)
        else:
            raw_str = ""

        if not raw_str.strip():
            return

        lines = [line.strip() for line in raw_str.splitlines() if line.strip()]
        first_line = lines[0] if lines else ""
        clean_aqi = first_line.split("\u2022")[0].split("\u00b7")[0].split("|")[0].strip()
        if not clean_aqi:
            return

        if clean_aqi.upper().startswith("AQI:"):
            display_aqi = f"AQI: {clean_aqi[4:].strip()}"
        elif clean_aqi.upper().startswith("AQI"):
            display_aqi = f"AQI: {clean_aqi[3:].strip()}"
        else:
            display_aqi = f"AQI: {clean_aqi}"

        if len(display_aqi) > 30:
            display_aqi = display_aqi[:30]

        f_aqi = self.get_font("bold", 10)
        tw, th = text_dims(draw, display_aqi, f_aqi)
        max_inner_w = (box_coords[2] - box_coords[0]) - 16
        if tw > max_inner_w:
            f_aqi = self.get_font("bold", 9)
            tw, th = text_dims(draw, display_aqi, f_aqi)
            while tw > max_inner_w and len(display_aqi) > 6:
                display_aqi = display_aqi[:-1]
                tw, th = text_dims(draw, display_aqi, f_aqi)

        aqi_x0, aqi_y0, aqi_x1, aqi_y1 = box_coords
        draw.rounded_rectangle([aqi_x0, aqi_y0, aqi_x1, aqi_y1], radius=11, fill=COLOR_BG, outline=COLOR_FG, width=1)
        draw.text(
            ((aqi_x0 + aqi_x1) // 2 - tw // 2, (aqi_y0 + aqi_y1) // 2 - th // 2 - 1),
            display_aqi,
            font=f_aqi,
            fill=COLOR_FG
        )

    def _draw_alert_banner(self, draw: ImageDraw.Draw, alert_text: str,
                           COLOR_FG: int, COLOR_BG: int,
                           box_coords: Tuple[int, int, int, int] = (320, 436, 764, 460)):
        pill_x0, pill_y0, pill_x1, pill_y1 = box_coords
        draw.rounded_rectangle([pill_x0, pill_y0, pill_x1, pill_y1], radius=6, fill=COLOR_FG)

        f_alert = self.get_font("bold", 12)
        max_w = (pill_x1 - pill_x0) - 20
        display_alert = alert_text
        while text_dims(draw, display_alert, f_alert)[0] > max_w and len(display_alert) > 10:
            display_alert = display_alert[:-4] + "..."

        aw, ah = text_dims(draw, display_alert, f_alert)
        draw.text(
            ((pill_x0 + pill_x1) // 2 - aw // 2, (pill_y0 + pill_y1) // 2 - ah // 2 - 1),
            display_alert,
            font=f_alert,
            fill=COLOR_BG
        )

    # =========================================================================
    # STYLE 1: CLASSIC (Default Editorial Hardware Layout)
    # =========================================================================
    def _render_classic(self, data: dict, is_dark: bool, hero_size: str,
                        alert_text: Optional[str] = None,
                        aqi_text: Optional[str] = None,
                        freshness_text: Optional[str] = None) -> Image.Image:
        COLOR_BG = 0 if is_dark else 255
        COLOR_FG = 255 if is_dark else 0
        COLOR_LINE = 165 if is_dark else 90
        COLOR_BAR = 95 if is_dark else 160

        Himage = Image.new('L', (SCREEN_WIDTH, SCREEN_HEIGHT), COLOR_BG)
        draw = ImageDraw.Draw(Himage)

        # SECTION 1: TOP 5-DAY FORECAST ROW (Bounds: 0..800, 16..134)
        top_y0 = 16
        top_y1 = 134
        col_widths = [168, 148, 148, 148, 148]
        col_starts = []
        curr_x = 20
        for w in col_widths:
            col_starts.append(curr_x)
            curr_x += w

        f_day = self.get_font("bold", 14)
        f_hi = self.get_font("bold", 16)
        f_lo = self.get_font("semibold", 14)

        for i, d in enumerate(data["days_data"]):
            if i >= len(col_widths):
                break
            cx = col_starts[i] + col_widths[i] // 2
            draw_centered_text(draw, cx, top_y0 + 4, d["name"], f_day, COLOR_FG)

            icon_img = self.load_weather_icon(d["icon"], size=(46, 46), dark_mode=is_dark)
            Himage.paste(icon_img, (cx - 23, top_y0 + 26))

            hi_str = f"{d['high']}{DEG}"
            lo_str = f"{d['low']}{DEG}"
            hw, _ = text_dims(draw, hi_str, f_hi)
            lw, _ = text_dims(draw, lo_str, f_lo)
            gap = 8
            tot_w = hw + gap + lw
            s_x = cx - tot_w // 2

            draw.text((s_x, top_y0 + 82), hi_str, font=f_hi, fill=COLOR_FG)
            draw.text((s_x + hw + gap, top_y0 + 84), lo_str, font=f_lo, fill=COLOR_FG)

            if i < len(data["days_data"]) - 1 and i < len(col_widths) - 1:
                div_x = col_starts[i + 1]
                draw_dashed_line(draw, div_x, top_y0 + 8, div_x, top_y1 - 8, dash=3, gap=3, fill=COLOR_FG, width=1)

        draw.line([(20, 138), (SCREEN_WIDTH - 20, 138)], fill=COLOR_FG, width=2)

        # SECTION 2: LEFT HERO CARD (card_y0 = 154, h = 314, radius = 12)
        card_x0, card_y0 = 20, 154
        card_w, card_h = 270, 314
        card_x1, card_y1 = card_x0 + card_w, card_y0 + card_h
        card_cx = card_x0 + card_w // 2

        draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=12, fill=COLOR_BG, outline=COLOR_FG, width=2)

        # 1. City: 26pt Bold
        f_city = self.get_font("bold", 26)
        draw_centered_text(draw, card_cx, card_y0 + 13, data["city_name"], f_city, COLOR_FG)

        # 2. Date + Moon Phase: 14pt SemiBold
        f_date = self.get_font("semibold", 14)
        dw, dh = text_dims(draw, data["date_str"], f_date)
        tot_date_w = dw + 8 + 14
        s_date_x = card_cx - tot_date_w // 2
        draw.text((s_date_x, card_y0 + 48), data["date_str"], font=f_date, fill=COLOR_FG)
        self.draw_lunar_phase(draw, s_date_x + dw + 15, card_y0 + 55, radius=6, phase=data["moon_phase"], fill=COLOR_FG, bg=COLOR_BG)

        # 3. Hero Temperature & Icon (Scalable by hero_size)
        cur_temp = data["cur_temp"]
        temp_str = f"{cur_temp}{DEG}"
        if hero_size == "compact":
            hero_pt = 44 if cur_temp >= 100 else 54
            h_icon_sz = (40, 40) if cur_temp >= 100 else (46, 46)
            icon_y = card_y0 + 74
            text_y = card_y0 + 70
        elif hero_size == "large":
            hero_pt = 68 if cur_temp >= 100 else 82
            h_icon_sz = (54, 54) if cur_temp >= 100 else (60, 60)
            icon_y = card_y0 + 68
            text_y = card_y0 + 64
        else:  # standard
            hero_pt = 54 if cur_temp >= 100 else 68
            h_icon_sz = (48, 48) if cur_temp >= 100 else (54, 54)
            icon_y = card_y0 + 74
            text_y = card_y0 + 68

        f_hero = self.get_font("bold", hero_pt)
        h_gap = 10
        tw, th = text_dims(draw, temp_str, f_hero)
        tot_hero_w = h_icon_sz[0] + h_gap + tw
        s_hero_x = card_cx - tot_hero_w // 2

        hero_icon = self.load_weather_icon(data["cur_icon"], size=h_icon_sz, dark_mode=is_dark)
        Himage.paste(hero_icon, (s_hero_x, icon_y))
        draw.text((s_hero_x + h_icon_sz[0] + h_gap, text_y), temp_str, font=f_hero, fill=COLOR_FG)

        # 4. Condition
        f_desc = self.get_font("bold", 21)
        draw_centered_text(draw, card_cx, card_y0 + 140, data["cur_desc"], f_desc, COLOR_FG)

        # 5. High | Low
        f_hl = self.get_font("bold", 16)
        hl_left = f"H {data['today_high']}{DEG}"
        hl_right = f"L {data['today_low']}{DEG}"
        hw, _ = text_dims(draw, hl_left, f_hl)
        draw.text((card_cx - 16 - hw, card_y0 + 168), hl_left, font=f_hl, fill=COLOR_FG)
        draw.line([(card_cx, card_y0 + 171), (card_cx, card_y0 + 185)], fill=COLOR_LINE, width=1)
        draw.text((card_cx + 16, card_y0 + 168), hl_right, font=f_hl, fill=COLOR_FG)

        # 6. Humidity | Wind
        f_meta = self.get_font("semibold", 13.5)
        y_meta = card_y0 + 196
        hum_txt = f"Humidity {data['humidity']}%"
        hw, _ = text_dims(draw, hum_txt, f_meta)
        tot_hum_w = 12 + 8 + hw
        s_hum_x = card_cx - 14 - tot_hum_w
        self.draw_droplet_icon(draw, s_hum_x + 6, y_meta + 8, r=4.5, fill=COLOR_FG)
        draw.text((s_hum_x + 18, y_meta), hum_txt, font=f_meta, fill=COLOR_FG)

        draw.line([(card_cx, y_meta + 3), (card_cx, y_meta + 16)], fill=COLOR_LINE, width=1)

        wind_txt = f"Wind {data['wind_str']}"
        s_wind_x = card_cx + 14
        self.draw_wind_icon(draw, s_wind_x + 8, y_meta + 8, w=15, fill=COLOR_FG)
        draw.text((s_wind_x + 22, y_meta), wind_txt, font=f_meta, fill=COLOR_FG)

        # 7. Sunrise | Sunset
        y_sun = card_y0 + 226
        sr_w, _ = text_dims(draw, data["sunrise_str"], f_meta)
        tot_sr_w = 18 + 8 + sr_w
        s_sr_x = card_cx - 14 - tot_sr_w
        self.draw_sunrise_icon(draw, s_sr_x + 9, y_sun + 8, r=5, fill=COLOR_FG)
        draw.text((s_sr_x + 24, y_sun), data["sunrise_str"], font=f_meta, fill=COLOR_FG)

        draw.line([(card_cx, y_sun + 3), (card_cx, y_sun + 16)], fill=COLOR_LINE, width=1)

        s_ss_x = card_cx + 14
        self.draw_sunset_icon(draw, s_ss_x + 9, y_sun + 8, r=5, fill=COLOR_FG)
        draw.text((s_ss_x + 24, y_sun), data["sunset_str"], font=f_meta, fill=COLOR_FG)

        # Subtle freshness indicator
        if freshness_text:
            f_fresh = self.get_font("semibold", 10)
            fw, fh = text_dims(draw, freshness_text, f_fresh)
            draw.text((card_cx - fw // 2, card_y0 + 242), freshness_text, font=f_fresh, fill=COLOR_FG)

        draw.line([(card_x0 + 16, card_y0 + 256), (card_x1 - 16, card_y0 + 256)], fill=COLOR_FG, width=1)

        # 8. Digital Clock
        f_clk = self.get_font("bold", 40)
        f_ampm = self.get_font("bold", 16)
        cw, ch = text_dims(draw, data["time_str"], f_clk)
        aw, ah = text_dims(draw, data["ampm_str"], f_ampm) if data["ampm_str"] else (0, 0)
        tot_clk_w = cw + (8 + aw if data["ampm_str"] else 0)
        s_clk_x = card_cx - tot_clk_w // 2

        draw.text((s_clk_x, card_y0 + 263), data["time_str"], font=f_clk, fill=COLOR_FG)
        if data["ampm_str"]:
            draw.text((s_clk_x + cw + 8, card_y0 + 274), data["ampm_str"], font=f_ampm, fill=COLOR_FG)

        # SECTION 3: RIGHT 24-HOUR FORECAST GRAPH CARD
        g_x0, g_y0 = 304, 154
        g_w, g_h = (SCREEN_WIDTH - 20) - g_x0, 314
        g_x1, g_y1 = g_x0 + g_w, g_y0 + g_h
        g_cx = g_x0 + g_w // 2

        draw.rounded_rectangle([g_x0, g_y0, g_x1, g_y1], radius=12, fill=COLOR_BG, outline=COLOR_FG, width=2)

        f_ghdr = self.get_font("bold", 14)
        draw_centered_text(draw, g_cx, g_y0 + 13, "24-HOUR FORECAST", f_ghdr, COLOR_FG)

        self._draw_aqi_badge(draw, aqi_text, COLOR_FG, COLOR_BG, (676, 162, 764, 184))

        plot_left = g_x0 + 39
        plot_right = g_x1 - 25
        plot_top = g_y0 + 64
        plot_bottom = g_y1 - 66
        plot_w = plot_right - plot_left
        plot_h = plot_bottom - plot_top

        hourly = data["hourly_entries"]
        if len(hourly) >= 4:
            temps = [t for _, t, _, _ in hourly]
            min_t, max_t = min(temps), max(temps)
            t_range = max_t - min_t if max_t != min_t else 2

            t_pad = max(2.0, t_range * 0.25)
            plot_min_t = min_t - t_pad
            plot_max_t = max_t + t_pad
            effective_range = plot_max_t - plot_min_t

            n_pts = len(hourly)
            xs, ys = [], []
            for i in range(n_pts):
                px = plot_left + int(i * (plot_w / (n_pts - 1)))
                py = int(plot_bottom - ((temps[i] - plot_min_t) / effective_range) * plot_h)
                xs.append(px)
                ys.append(py)

            for i in range(n_pts):
                rain_mm = hourly[i][2]
                if rain_mm > 0.1:
                    bar_x0 = xs[i] - 12
                    bar_x1 = xs[i] + 12
                    bar_height = min(28, int(rain_mm * 6))
                    bar_y0 = plot_bottom - bar_height
                    bar_y1 = plot_bottom
                    draw.rectangle([bar_x0, bar_y0, bar_x1, bar_y1], fill=COLOR_BAR)
                    draw.rectangle([bar_x0, bar_y0, bar_x1, bar_y1], outline=COLOR_FG, width=1)

            try:
                a, b, c, d, h = cubic_spline_coeffs(xs, ys)
                x_fine = np.linspace(xs[0], xs[-1], 250)
                y_fine = [eval_spline(a, b, c, d, h, xs, xi) for xi in x_fine]
                for k in range(len(x_fine) - 1):
                    draw.line([(x_fine[k], y_fine[k]), (x_fine[k + 1], y_fine[k + 1])], fill=COLOR_FG, width=3)
            except Exception:
                for k in range(len(xs) - 1):
                    draw.line([(xs[k], ys[k]), (xs[k + 1], ys[k + 1])], fill=COLOR_FG, width=3)

            f_temp_lbl = self.get_font("bold", 17)
            f_hour_lbl = self.get_font("bold", 13)
            f_pop_lbl = self.get_font("bold", 11)

            for i, (item_dt, t_val, rain_mm, pop_val) in enumerate(hourly):
                px, py = xs[i], ys[i]
                if py + 7 < plot_bottom:
                    draw_dashed_line(draw, px, py + 7, px, plot_bottom, dash=2, gap=3, fill=COLOR_FG, width=1)

                t_str = f"{round(t_val)}{DEG}"
                tw, th = text_dims(draw, t_str, f_temp_lbl)
                tx = px - tw // 2
                ty = py - 27
                draw.rectangle([tx - 3, ty - 2, tx + tw + 3, ty + th + 2], fill=COLOR_BG)
                draw.text((tx, ty), t_str, font=f_temp_lbl, fill=COLOR_FG)

                r = 5
                draw.ellipse([px - r, py - r, px + r, py + r], fill=COLOR_BG, outline=COLOR_FG, width=2)

                if i == 0:
                    h_str = "NOW"
                else:
                    if data["use_24h"]:
                        h_str = item_dt.strftime("%H:%M")
                    else:
                        h_str = item_dt.strftime("%I %p").lstrip("0").replace(" 0", " ")

                hw, hh = text_dims(draw, h_str, f_hour_lbl)
                hx = px - hw // 2
                hy = plot_bottom + 14
                draw.rectangle([hx - 2, hy - 1, hx + hw + 2, hy + hh + 1], fill=COLOR_BG)
                draw.text((hx, hy), h_str, font=f_hour_lbl, fill=COLOR_FG)

                if pop_val >= 15 and not alert_text:
                    pop_txt = f"{pop_val}%"
                    tw, _ = text_dims(draw, pop_txt, f_pop_lbl)
                    drop_total_w = 8 + 4 + tw
                    start_x = px - drop_total_w // 2
                    draw_droplet(draw, start_x + 4, plot_bottom + 34, size=7, fill=COLOR_FG)
                    draw.text((start_x + 11, plot_bottom + 27), pop_txt, font=f_pop_lbl, fill=COLOR_FG)

        if alert_text:
            self._draw_alert_banner(draw, alert_text, COLOR_FG, COLOR_BG, (g_x0 + 16, g_y1 - 32, g_x1 - 16, g_y1 - 8))

        return Himage

    # =========================================================================
    # STYLE 2: WIDGETS (Tactile Grid Layout with 2x2 Metric Tiles)
    # =========================================================================
    def _render_widgets(self, data: dict, is_dark: bool, hero_size: str,
                        alert_text: Optional[str] = None,
                        aqi_text: Optional[str] = None,
                        freshness_text: Optional[str] = None) -> Image.Image:
        COLOR_BG = 0 if is_dark else 255
        COLOR_FG = 255 if is_dark else 0
        COLOR_LINE = 165 if is_dark else 90

        Himage = Image.new('L', (SCREEN_WIDTH, SCREEN_HEIGHT), COLOR_BG)
        draw = ImageDraw.Draw(Himage)

        # Top 5-Day Forecast Bar
        bar_left, bar_right = 16, SCREEN_WIDTH - 16
        num_days = min(5, len(data["days_data"]))
        if num_days > 0:
            col_w = (bar_right - bar_left) // num_days
            f_day = self.get_font("bold", 16)
            f_hl = self.get_font("bold", 18)
            for i in range(num_days):
                d = data["days_data"][i]
                cx = bar_left + i * col_w + col_w // 2
                draw_centered_text(draw, cx, 14, d["name"], f_day, COLOR_FG)

                icon_img = self.load_weather_icon(d["icon"], size=(54, 54), dark_mode=is_dark)
                Himage.paste(icon_img, (cx - 27, 38))

                hl_str = f"{d['high']}{DEG}  {d['low']}{DEG}"
                draw_centered_text(draw, cx, 102, hl_str, f_hl, COLOR_FG)

                if i < num_days - 1:
                    div_x = bar_left + (i + 1) * col_w
                    draw.line([(div_x, 16), (div_x, 134)], fill=COLOR_LINE, width=1)

        draw.line([(16, 144), (SCREEN_WIDTH - 16, 144)], fill=COLOR_FG, width=2)

        # Left Hero Widget Card
        c_x0, c_y0 = 16, 156
        c_w, c_h = 320, 312
        c_x1, c_y1 = c_x0 + c_w, c_y0 + c_h
        draw.rounded_rectangle([c_x0, c_y0, c_x1, c_y1], radius=14, fill=COLOR_BG, outline=COLOR_FG, width=2)

        # City & Date Header
        f_city = self.get_font("bold", 20)
        f_date = self.get_font("semibold", 14)
        draw.text((c_x0 + 16, c_y0 + 12), data["city_name"].upper(), font=f_city, fill=COLOR_FG)
        dw, _ = text_dims(draw, data["date_str"], f_date)
        draw.text((c_x1 - 16 - dw, c_y0 + 15), data["date_str"], font=f_date, fill=COLOR_FG)

        draw.line([(c_x0 + 14, c_y0 + 40), (c_x1 - 14, c_y0 + 40)], fill=COLOR_LINE, width=1)

        # Hero Temp + Icon + Clock Row
        cur_temp = data["cur_temp"]
        if hero_size == "compact":
            hero_pt = 40 if cur_temp >= 100 else 48
            icon_sz = (44, 44)
        elif hero_size == "large":
            hero_pt = 56 if cur_temp >= 100 else 66
            icon_sz = (54, 54)
        else:
            hero_pt = 48 if cur_temp >= 100 else 56
            icon_sz = (50, 50)

        hero_icon = self.load_weather_icon(data["cur_icon"], size=icon_sz, dark_mode=is_dark)
        Himage.paste(hero_icon, (c_x0 + 16, c_y0 + 48))

        f_temp = self.get_font("bold", hero_pt)
        draw.text((c_x0 + 20 + icon_sz[0], c_y0 + 44), f"{cur_temp}{DEG}", font=f_temp, fill=COLOR_FG)

        # Clock in upper-right of hero card
        f_clk = self.get_font("bold", 30)
        f_apm = self.get_font("bold", 14)
        cw, _ = text_dims(draw, data["time_str"], f_clk)
        aw, _ = text_dims(draw, data["ampm_str"], f_apm) if data["ampm_str"] else (0, 0)
        clk_rx = c_x1 - 16
        draw.text((clk_rx - (cw + (4 + aw if aw else 0)), c_y0 + 52), data["time_str"], font=f_clk, fill=COLOR_FG)
        if data["ampm_str"]:
            draw.text((clk_rx - aw, c_y0 + 54), data["ampm_str"], font=f_apm, fill=COLOR_FG)

        # Condition & H/L
        f_desc = self.get_font("bold", 15)
        desc_str = f"{data['cur_desc'].upper()} \u2022 H {data['today_high']}{DEG} / L {data['today_low']}{DEG}"
        draw.text((c_x0 + 16, c_y0 + 110), desc_str, font=f_desc, fill=COLOR_FG)

        draw.line([(c_x0 + 14, c_y0 + 134), (c_x1 - 14, c_y0 + 134)], fill=COLOR_LINE, width=1)

        # 2x2 Metric Tiles
        aqi_label = "Good"
        if aqi_text and not isinstance(aqi_text, bool):
            aqi_str = str(aqi_text).split("\u2022")[0].replace("AQI:", "").strip()
            if aqi_str:
                aqi_label = aqi_str[:12]

        tiles = [
            ("HUMIDITY", f"{data['humidity']}%"),
            ("WIND SPEED", data["wind_str"]),
            ("AIR QUALITY", aqi_label),
            ("SUNRISE", data["sunrise_str"])
        ]
        t_w = (c_w - 44) // 2
        t_h = 64
        t_coords = [
            (c_x0 + 16, c_y0 + 146),
            (c_x0 + 16 + t_w + 12, c_y0 + 146),
            (c_x0 + 16, c_y0 + 146 + t_h + 10),
            (c_x0 + 16 + t_w + 12, c_y0 + 146 + t_h + 10),
        ]
        f_tlbl = self.get_font("bold", 11)
        f_tval = self.get_font("bold", 17)

        for (tx, ty), (lbl, val) in zip(t_coords, tiles):
            draw.rounded_rectangle([tx, ty, tx + t_w, ty + t_h], radius=8, fill=COLOR_BG, outline=COLOR_FG, width=1)
            draw.text((tx + 10, ty + 8), lbl, font=f_tlbl, fill=COLOR_FG)
            draw.text((tx + 10, ty + 30), val, font=f_tval, fill=COLOR_FG)

        if freshness_text:
            f_fresh = self.get_font("semibold", 10)
            fw, _ = text_dims(draw, freshness_text, f_fresh)
            draw.text((c_x0 + c_w // 2 - fw // 2, c_y1 - 16), freshness_text, font=f_fresh, fill=COLOR_FG)

        # Right Graph Card
        g_x0, g_y0 = 352, 156
        g_w = SCREEN_WIDTH - g_x0 - 16
        g_x1, g_y1 = g_x0 + g_w, c_y0 + 312
        draw.rounded_rectangle([g_x0, g_y0, g_x1, g_y1], radius=14, fill=COLOR_BG, outline=COLOR_FG, width=2)
        draw.text((g_x0 + 18, g_y0 + 14), "24-HOUR FORECAST", font=self.get_font("bold", 15), fill=COLOR_FG)
        self._draw_aqi_badge(draw, aqi_text, COLOR_FG, COLOR_BG, (g_x1 - 106, g_y0 + 10, g_x1 - 16, g_y0 + 32))

        p_left, p_right = g_x0 + 30, g_x1 - 26
        p_top, p_bot = g_y0 + 64, g_y1 - 60
        p_w, p_h = p_right - p_left, p_bot - p_top

        hourly = data["hourly_entries"]
        if len(hourly) >= 4:
            temps = [t for _, t, _, _ in hourly]
            min_t, max_t = min(temps), max(temps)
            t_range = max_t - min_t if max_t != min_t else 2
            t_pad = max(2.0, t_range * 0.25)
            plot_min_t = min_t - t_pad
            plot_max_t = max_t + t_pad
            effective_range = plot_max_t - plot_min_t

            n_pts = len(hourly)
            xs, ys = [], []
            for i in range(n_pts):
                px = p_left + int(i * (p_w / (n_pts - 1)))
                py = int(p_bot - ((temps[i] - plot_min_t) / effective_range) * p_h)
                xs.append(px)
                ys.append(py)

            try:
                a, b, c, d, h = cubic_spline_coeffs(xs, ys)
                xf = np.linspace(xs[0], xs[-1], 200)
                yf = [eval_spline(a, b, c, d, h, xs, xi) for xi in xf]
                for k in range(len(xf) - 1):
                    draw.line([(xf[k], yf[k]), (xf[k + 1], yf[k + 1])], fill=COLOR_FG, width=3)
            except Exception:
                for k in range(len(xs) - 1):
                    draw.line([(xs[k], ys[k]), (xs[k + 1], ys[k + 1])], fill=COLOR_FG, width=3)

            f_temp_lbl = self.get_font("bold", 16)
            f_hour_lbl = self.get_font("bold", 13)
            f_pop_lbl = self.get_font("bold", 11)

            for i, (item_dt, t_val, rain_mm, pop_val) in enumerate(hourly):
                px, py = xs[i], ys[i]
                if py + 7 < p_bot:
                    draw_dashed_line(draw, px, py + 7, px, p_bot, dash=2, gap=3, fill=COLOR_FG, width=1)

                t_str = f"{round(t_val)}{DEG}"
                tw, th = text_dims(draw, t_str, f_temp_lbl)
                draw.rectangle([px - tw // 2 - 2, py - 26, px + tw // 2 + 2, py - 8], fill=COLOR_BG)
                draw.text((px - tw // 2, py - 25), t_str, font=f_temp_lbl, fill=COLOR_FG)

                draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=COLOR_BG, outline=COLOR_FG, width=2)

                if i == 0:
                    h_str = "NOW"
                else:
                    h_str = item_dt.strftime("%H:%M") if data["use_24h"] else item_dt.strftime("%I %p").lstrip("0")

                hw, _ = text_dims(draw, h_str, f_hour_lbl)
                draw.rectangle([px - hw // 2 - 2, p_bot + 12, px + hw // 2 + 2, p_bot + 28], fill=COLOR_BG)
                draw.text((px - hw // 2, p_bot + 13), h_str, font=f_hour_lbl, fill=COLOR_FG)

                if pop_val >= 15 and not alert_text:
                    pop_txt = f"{pop_val}%"
                    pw, _ = text_dims(draw, pop_txt, f_pop_lbl)
                    start_x = px - (8 + 3 + pw) // 2
                    draw_droplet(draw, start_x + 3, p_bot + 33, size=7, fill=COLOR_FG)
                    draw.text((start_x + 10, p_bot + 26), pop_txt, font=f_pop_lbl, fill=COLOR_FG)

        if alert_text:
            self._draw_alert_banner(draw, alert_text, COLOR_FG, COLOR_BG, (g_x0 + 16, g_y1 - 32, g_x1 - 16, g_y1 - 8))

        return Himage

    # =========================================================================
    # STYLE 3: DUAL-TONE (Inverted High-Contrast Hero Card)
    # =========================================================================
    def _render_dualtone(self, data: dict, is_dark: bool, hero_size: str,
                         alert_text: Optional[str] = None,
                         aqi_text: Optional[str] = None,
                         freshness_text: Optional[str] = None) -> Image.Image:
        COLOR_BG = 0 if is_dark else 255
        COLOR_FG = 255 if is_dark else 0
        COLOR_LINE = 165 if is_dark else 90

        Himage = Image.new('L', (SCREEN_WIDTH, SCREEN_HEIGHT), COLOR_BG)
        draw = ImageDraw.Draw(Himage)

        # Top 5-Day Forecast Row
        bar_left, bar_right = 16, SCREEN_WIDTH - 16
        num_days = min(5, len(data["days_data"]))
        if num_days > 0:
            col_w = (bar_right - bar_left) // num_days
            f_day = self.get_font("bold", 15)
            f_hl = self.get_font("bold", 17)
            for i in range(num_days):
                d = data["days_data"][i]
                cx = bar_left + i * col_w + col_w // 2
                draw_centered_text(draw, cx, 14, d["name"], f_day, COLOR_FG)

                icon_img = self.load_weather_icon(d["icon"], size=(50, 50), dark_mode=is_dark)
                Himage.paste(icon_img, (cx - 25, 36))

                hl_str = f"{d['high']}{DEG}  {d['low']}{DEG}"
                draw_centered_text(draw, cx, 98, hl_str, f_hl, COLOR_FG)

                if i < num_days - 1:
                    div_x = bar_left + (i + 1) * col_w
                    draw.line([(div_x, 16), (div_x, 130)], fill=COLOR_LINE, width=1)

        draw.line([(16, 140), (SCREEN_WIDTH - 16, 140)], fill=COLOR_FG, width=2)

        # Left Hero Card: Solid Inverted Card (Black on white or White on black)
        c_x0, c_y0 = 16, 154
        c_w, c_h = 300, 314
        c_x1, c_y1 = c_x0 + c_w, c_y0 + c_h
        c_cx = c_x0 + c_w // 2

        # Draw inverted solid card
        draw.rounded_rectangle([c_x0, c_y0, c_x1, c_y1], radius=14, fill=COLOR_FG, outline=COLOR_FG, width=2)

        # All typography inside hero card uses COLOR_BG
        f_city = self.get_font("bold", 24)
        draw_centered_text(draw, c_cx, c_y0 + 14, data["city_name"].upper(), f_city, COLOR_BG)

        f_date = self.get_font("semibold", 14)
        draw_centered_text(draw, c_cx, c_y0 + 44, data["date_str"], f_date, COLOR_BG)

        cur_temp = data["cur_temp"]
        temp_str = f"{cur_temp}{DEG}"
        if hero_size == "compact":
            hero_pt = 44 if cur_temp >= 100 else 54
            icon_sz = (46, 46)
        elif hero_size == "large":
            hero_pt = 68 if cur_temp >= 100 else 82
            icon_sz = (58, 58)
        else:
            hero_pt = 54 if cur_temp >= 100 else 68
            icon_sz = (52, 52)

        # Icon inside inverted card must invert polarity
        inv_icon = self.load_weather_icon(data["cur_icon"], size=icon_sz, dark_mode=(not is_dark))
        f_hero = self.get_font("bold", hero_pt)
        tw, _ = text_dims(draw, temp_str, f_hero)
        b_w = icon_sz[0] + 10 + tw
        b_sx = c_cx - b_w // 2
        Himage.paste(inv_icon, (b_sx, c_y0 + 72))
        draw.text((b_sx + icon_sz[0] + 10, c_y0 + 66), temp_str, font=f_hero, fill=COLOR_BG)

        f_desc = self.get_font("bold", 15)
        desc_line = f"{data['cur_desc'].upper()} \u2022 H {data['today_high']}{DEG}  L {data['today_low']}{DEG}"
        draw_centered_text(draw, c_cx, c_y0 + 142, desc_line, f_desc, COLOR_BG)

        f_meta = self.get_font("semibold", 13)
        meta_line = f"Humidity {data['humidity']}%   Wind {data['wind_str']}"
        draw_centered_text(draw, c_cx, c_y0 + 168, meta_line, f_meta, COLOR_BG)

        sr_ss = f"Sunrise {data['sunrise_str']}  \u2022  Sunset {data['sunset_str']}"
        draw_centered_text(draw, c_cx, c_y0 + 192, sr_ss, f_meta, COLOR_BG)

        draw.line([(c_x0 + 18, c_y0 + 220), (c_x1 - 18, c_y0 + 220)], fill=COLOR_BG, width=1)

        # Inverted Clock
        f_clk = self.get_font("bold", 42)
        f_apm = self.get_font("bold", 16)
        cw, _ = text_dims(draw, data["time_str"], f_clk)
        aw, _ = text_dims(draw, data["ampm_str"], f_apm) if data["ampm_str"] else (0, 0)
        tot_cw = cw + (8 + aw if aw else 0)
        csx = c_cx - tot_cw // 2
        draw.text((csx, c_y0 + 236), data["time_str"], font=f_clk, fill=COLOR_BG)
        if data["ampm_str"]:
            draw.text((csx + cw + 8, c_y0 + 250), data["ampm_str"], font=f_apm, fill=COLOR_BG)

        if freshness_text:
            f_fresh = self.get_font("semibold", 10)
            fw, _ = text_dims(draw, freshness_text, f_fresh)
            draw.text((c_cx - fw // 2, c_y1 - 16), freshness_text, font=f_fresh, fill=COLOR_BG)

        # Right Graph Card
        g_x0 = 332
        g_w = SCREEN_WIDTH - g_x0 - 16
        g_x1, g_y1 = g_x0 + g_w, c_y0 + 314
        draw.rounded_rectangle([g_x0, c_y0, g_x1, g_y1], radius=14, fill=COLOR_BG, outline=COLOR_FG, width=2)
        draw.text((g_x0 + 20, c_y0 + 14), "24-HOUR FORECAST", font=self.get_font("bold", 15), fill=COLOR_FG)
        self._draw_aqi_badge(draw, aqi_text, COLOR_FG, COLOR_BG, (g_x1 - 106, c_y0 + 10, g_x1 - 16, c_y0 + 32))

        p_left, p_right = g_x0 + 32, g_x1 - 24
        p_top, p_bot = c_y0 + 64, g_y1 - 60
        p_w, p_h = p_right - p_left, p_bot - p_top

        hourly = data["hourly_entries"]
        if len(hourly) >= 4:
            temps = [t for _, t, _, _ in hourly]
            min_t, max_t = min(temps), max(temps)
            t_range = max_t - min_t if max_t != min_t else 2
            t_pad = max(2.0, t_range * 0.25)
            plot_min_t = min_t - t_pad
            plot_max_t = max_t + t_pad
            effective_range = plot_max_t - plot_min_t

            n_pts = len(hourly)
            xs, ys = [], []
            for i in range(n_pts):
                px = p_left + int(i * (p_w / (n_pts - 1)))
                py = int(p_bot - ((temps[i] - plot_min_t) / effective_range) * p_h)
                xs.append(px)
                ys.append(py)

            try:
                a, b, c, d, h = cubic_spline_coeffs(xs, ys)
                xf = np.linspace(xs[0], xs[-1], 200)
                yf = [eval_spline(a, b, c, d, h, xs, xi) for xi in xf]
                for k in range(len(xf) - 1):
                    draw.line([(xf[k], yf[k]), (xf[k + 1], yf[k + 1])], fill=COLOR_FG, width=3)
            except Exception:
                for k in range(len(xs) - 1):
                    draw.line([(xs[k], ys[k]), (xs[k + 1], ys[k + 1])], fill=COLOR_FG, width=3)

            f_temp_lbl = self.get_font("bold", 16)
            f_hour_lbl = self.get_font("bold", 13)
            f_pop_lbl = self.get_font("bold", 11)

            for i, (item_dt, t_val, rain_mm, pop_val) in enumerate(hourly):
                px, py = xs[i], ys[i]
                if py + 7 < p_bot:
                    draw_dashed_line(draw, px, py + 7, px, p_bot, dash=2, gap=3, fill=COLOR_FG, width=1)

                t_str = f"{round(t_val)}{DEG}"
                tw, th = text_dims(draw, t_str, f_temp_lbl)
                draw.rectangle([px - tw // 2 - 2, py - 26, px + tw // 2 + 2, py - 8], fill=COLOR_BG)
                draw.text((px - tw // 2, py - 25), t_str, font=f_temp_lbl, fill=COLOR_FG)

                draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=COLOR_BG, outline=COLOR_FG, width=2)

                if i == 0:
                    h_str = "NOW"
                else:
                    h_str = item_dt.strftime("%H:%M") if data["use_24h"] else item_dt.strftime("%I %p").lstrip("0")

                hw, _ = text_dims(draw, h_str, f_hour_lbl)
                draw.rectangle([px - hw // 2 - 2, p_bot + 12, px + hw // 2 + 2, p_bot + 28], fill=COLOR_BG)
                draw.text((px - hw // 2, p_bot + 13), h_str, font=f_hour_lbl, fill=COLOR_FG)

                if pop_val >= 15 and not alert_text:
                    pop_txt = f"{pop_val}%"
                    pw, _ = text_dims(draw, pop_txt, f_pop_lbl)
                    start_x = px - (8 + 3 + pw) // 2
                    draw_droplet(draw, start_x + 3, p_bot + 33, size=7, fill=COLOR_FG)
                    draw.text((start_x + 10, p_bot + 26), pop_txt, font=f_pop_lbl, fill=COLOR_FG)

        if alert_text:
            self._draw_alert_banner(draw, alert_text, COLOR_FG, COLOR_BG, (g_x0 + 16, g_y1 - 32, g_x1 - 16, g_y1 - 8))

        return Himage

    # =========================================================================
    # STYLE 4: MINIMALIST (Scandinavian Chiclet & Clean Typography)
    # =========================================================================
    def _render_minimalist(self, data: dict, is_dark: bool, hero_size: str,
                           alert_text: Optional[str] = None,
                           aqi_text: Optional[str] = None,
                           freshness_text: Optional[str] = None) -> Image.Image:
        COLOR_BG = 0 if is_dark else 255
        COLOR_FG = 255 if is_dark else 0
        COLOR_LINE = 165 if is_dark else 90

        Himage = Image.new('L', (SCREEN_WIDTH, SCREEN_HEIGHT), COLOR_BG)
        draw = ImageDraw.Draw(Himage)

        # Precision corner registration markings [+]
        for gx in [14, SCREEN_WIDTH - 14]:
            for gy in [14, SCREEN_HEIGHT - 14]:
                draw.line([(gx - 4, gy), (gx + 4, gy)], fill=COLOR_LINE, width=1)
                draw.line([(gx, gy - 4), (gx, gy + 4)], fill=COLOR_LINE, width=1)

        # Section 1: Tactile Chiclet Keycaps for 5-Day Forecast
        num_days = min(5, len(data["days_data"]))
        if num_days > 0:
            bar_y0, bar_h = 14, 126
            col_w = 144
            gap = 10
            total_w = num_days * col_w + (num_days - 1) * gap
            start_x = (SCREEN_WIDTH - total_w) // 2

            for i in range(num_days):
                d = data["days_data"][i]
                kx0 = start_x + i * (col_w + gap)
                kx1 = kx0 + col_w
                ky0 = bar_y0
                ky1 = bar_y0 + bar_h
                cx = (kx0 + kx1) // 2
                is_today = (i == 0)

                if is_today:
                    draw.rounded_rectangle([kx0, ky0, kx1, ky1], radius=10, fill=COLOR_FG, outline=COLOR_FG, width=1)
                    draw_centered_text(draw, cx, ky0 + 8, "TODAY", self.get_font("bold", 14), COLOR_BG)

                    icon_img = self.load_weather_icon(d["icon"], size=(44, 44), dark_mode=(not is_dark))
                    Himage.paste(icon_img, (cx - 22, ky0 + 30))

                    pill_y0, pill_y1 = ky1 - 36, ky1 - 8
                    draw.rounded_rectangle([kx0 + 8, pill_y0, kx1 - 8, pill_y1], radius=6, fill=COLOR_BG)
                    hl_str = f"{d['high']}{DEG}  {d['low']}{DEG}"
                    draw_centered_text(draw, cx, pill_y0 + 5, hl_str, self.get_font("bold", 15), COLOR_FG)
                else:
                    draw.rounded_rectangle([kx0, ky0, kx1, ky1], radius=10, fill=COLOR_BG, outline=COLOR_FG, width=1)
                    draw_centered_text(draw, cx, ky0 + 8, d["name"], self.get_font("bold", 14), COLOR_FG)

                    icon_img = self.load_weather_icon(d["icon"], size=(44, 44), dark_mode=is_dark)
                    Himage.paste(icon_img, (cx - 22, ky0 + 30))

                    pill_y0, pill_y1 = ky1 - 36, ky1 - 8
                    draw.rounded_rectangle([kx0 + 8, pill_y0, kx1 - 8, pill_y1], radius=6, fill=COLOR_BG, outline=COLOR_LINE, width=1)
                    hl_str = f"{d['high']}{DEG}  {d['low']}{DEG}"
                    draw_centered_text(draw, cx, pill_y0 + 5, hl_str, self.get_font("bold", 15), COLOR_FG)

        # Section 2: Borderless Scandinavian Left Card
        c_x0, c_y0 = 24, 154
        c_w, c_h = 280, 314
        c_cx = c_x0 + c_w // 2

        # City Name & Date
        draw_centered_text(draw, c_cx, c_y0 + 8, data["city_name"].upper(), self.get_font("bold", 24), COLOR_FG)

        f_date = self.get_font("semibold", 14)
        dw, _ = text_dims(draw, data["date_str"], f_date)
        s_date_x = c_cx - (dw + 22) // 2
        draw.text((s_date_x, c_y0 + 38), data["date_str"], font=f_date, fill=COLOR_FG)
        self.draw_lunar_phase(draw, s_date_x + dw + 14, c_y0 + 45, radius=6, phase=data["moon_phase"], fill=COLOR_FG, bg=COLOR_BG)

        # Hero Temperature & Icon
        cur_temp = data["cur_temp"]
        temp_str = f"{cur_temp}{DEG}"
        if hero_size == "compact":
            hero_pt = 44 if cur_temp >= 100 else 54
            icon_sz = (44, 44)
        elif hero_size == "large":
            hero_pt = 68 if cur_temp >= 100 else 82
            icon_sz = (58, 58)
        else:
            hero_pt = 54 if cur_temp >= 100 else 68
            icon_sz = (52, 52)

        f_hero = self.get_font("bold", hero_pt)
        tw, _ = text_dims(draw, temp_str, f_hero)
        tot_w = icon_sz[0] + 10 + tw
        s_hero_x = c_cx - tot_w // 2

        hero_icon = self.load_weather_icon(data["cur_icon"], size=icon_sz, dark_mode=is_dark)
        Himage.paste(hero_icon, (s_hero_x, c_y0 + 68))
        draw.text((s_hero_x + icon_sz[0] + 10, c_y0 + 62), temp_str, font=f_hero, fill=COLOR_FG)

        # Condition
        draw_centered_text(draw, c_cx, c_y0 + 136, data["cur_desc"], self.get_font("bold", 18), COLOR_FG)

        # High/Low & Metrics
        hl_line = f"High {data['today_high']}{DEG}  \u2022  Low {data['today_low']}{DEG}"
        draw_centered_text(draw, c_cx, c_y0 + 164, hl_line, self.get_font("semibold", 14), COLOR_FG)

        meta_line = f"Humidity {data['humidity']}%   Wind {data['wind_str']}"
        draw_centered_text(draw, c_cx, c_y0 + 188, meta_line, self.get_font("semibold", 13), COLOR_FG)

        sr_line = f"\u2600 {data['sunrise_str']}   \u263d {data['sunset_str']}"
        draw_centered_text(draw, c_cx, c_y0 + 212, sr_line, self.get_font("semibold", 13), COLOR_FG)

        draw.line([(c_x0 + 20, c_y0 + 238), (c_x0 + c_w - 20, c_y0 + 238)], fill=COLOR_LINE, width=1)

        # Clock
        f_clk = self.get_font("bold", 42)
        f_apm = self.get_font("bold", 16)
        cw, _ = text_dims(draw, data["time_str"], f_clk)
        aw, _ = text_dims(draw, data["ampm_str"], f_apm) if data["ampm_str"] else (0, 0)
        tot_cw = cw + (8 + aw if aw else 0)
        csx = c_cx - tot_cw // 2
        draw.text((csx, c_y0 + 250), data["time_str"], font=f_clk, fill=COLOR_FG)
        if data["ampm_str"]:
            draw.text((csx + cw + 8, c_y0 + 262), data["ampm_str"], font=f_apm, fill=COLOR_FG)

        if freshness_text:
            f_fresh = self.get_font("semibold", 10)
            fw, _ = text_dims(draw, freshness_text, f_fresh)
            draw.text((c_cx - fw // 2, c_y0 + 298), freshness_text, font=f_fresh, fill=COLOR_FG)

        # Section 3: Right 24-Hour Graph Card
        g_x0, g_y0 = 324, 154
        g_w = SCREEN_WIDTH - g_x0 - 24
        g_x1, g_y1 = g_x0 + g_w, c_y0 + 314
        draw.rounded_rectangle([g_x0, g_y0, g_x1, g_y1], radius=12, fill=COLOR_BG, outline=COLOR_FG, width=1)
        draw.text((g_x0 + 20, g_y0 + 14), "24-HOUR TREND", font=self.get_font("bold", 15), fill=COLOR_FG)
        self._draw_aqi_badge(draw, aqi_text, COLOR_FG, COLOR_BG, (g_x1 - 106, g_y0 + 10, g_x1 - 16, g_y0 + 32))

        p_left, p_right = g_x0 + 34, g_x1 - 24
        p_top, p_bot = g_y0 + 64, g_y1 - 60
        p_w, p_h = p_right - p_left, p_bot - p_top

        hourly = data["hourly_entries"]
        if len(hourly) >= 4:
            temps = [t for _, t, _, _ in hourly]
            min_t, max_t = min(temps), max(temps)
            t_range = max_t - min_t if max_t != min_t else 2
            t_pad = max(2.0, t_range * 0.25)
            plot_min_t = min_t - t_pad
            plot_max_t = max_t + t_pad
            effective_range = plot_max_t - plot_min_t

            n_pts = len(hourly)
            xs, ys = [], []
            for i in range(n_pts):
                px = p_left + int(i * (p_w / (n_pts - 1)))
                py = int(p_bot - ((temps[i] - plot_min_t) / effective_range) * p_h)
                xs.append(px)
                ys.append(py)

            try:
                a, b, c, d, h = cubic_spline_coeffs(xs, ys)
                xf = np.linspace(xs[0], xs[-1], 200)
                yf = [eval_spline(a, b, c, d, h, xs, xi) for xi in xf]
                for k in range(len(xf) - 1):
                    draw.line([(xf[k], yf[k]), (xf[k + 1], yf[k + 1])], fill=COLOR_FG, width=3)
            except Exception:
                for k in range(len(xs) - 1):
                    draw.line([(xs[k], ys[k]), (xs[k + 1], ys[k + 1])], fill=COLOR_FG, width=3)

            f_temp_lbl = self.get_font("bold", 16)
            f_hour_lbl = self.get_font("bold", 13)
            f_pop_lbl = self.get_font("bold", 11)

            for i, (item_dt, t_val, rain_mm, pop_val) in enumerate(hourly):
                px, py = xs[i], ys[i]
                if py + 7 < p_bot:
                    draw_dashed_line(draw, px, py + 7, px, p_bot, dash=2, gap=3, fill=COLOR_FG, width=1)

                t_str = f"{round(t_val)}{DEG}"
                tw, th = text_dims(draw, t_str, f_temp_lbl)
                draw.rectangle([px - tw // 2 - 2, py - 26, px + tw // 2 + 2, py - 8], fill=COLOR_BG)
                draw.text((px - tw // 2, py - 25), t_str, font=f_temp_lbl, fill=COLOR_FG)

                draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=COLOR_BG, outline=COLOR_FG, width=2)

                if i == 0:
                    h_str = "NOW"
                else:
                    h_str = item_dt.strftime("%H:%M") if data["use_24h"] else item_dt.strftime("%I %p").lstrip("0")

                hw, _ = text_dims(draw, h_str, f_hour_lbl)
                draw.rectangle([px - hw // 2 - 2, p_bot + 12, px + hw // 2 + 2, p_bot + 28], fill=COLOR_BG)
                draw.text((px - hw // 2, p_bot + 13), h_str, font=f_hour_lbl, fill=COLOR_FG)

                if pop_val >= 15 and not alert_text:
                    pop_txt = f"{pop_val}%"
                    pw, _ = text_dims(draw, pop_txt, f_pop_lbl)
                    start_x = px - (8 + 3 + pw) // 2
                    draw_droplet(draw, start_x + 3, p_bot + 33, size=7, fill=COLOR_FG)
                    draw.text((start_x + 10, p_bot + 26), pop_txt, font=f_pop_lbl, fill=COLOR_FG)

        if alert_text:
            self._draw_alert_banner(draw, alert_text, COLOR_FG, COLOR_BG, (g_x0 + 16, g_y1 - 32, g_x1 - 16, g_y1 - 8))

        return Himage

    # =========================================================================
    # PRIMARY DISPATCH RENDER METHOD
    # =========================================================================
    def render(self, forecast_data: dict, current_data: dict, alert_text: Optional[str] = None,
               aqi_text: Optional[str] = None, kcno_obs: Optional[dict] = None,
               freshness_text: Optional[str] = None,
               settings: Optional[dict] = None,
               dark_mode: Optional[Union[bool, str]] = None,
               layout_style: Optional[str] = None,
               hero_size: Optional[str] = None) -> Image.Image:
        """
        Renders the complete 800x480 dashboard according to layout style and hero size.
        """
        cfg = settings or {}
        w_cfg = cfg.get("weather", {})
        d_cfg = cfg.get("display", {})

        use_metric = w_cfg.get("use_metric", False)
        display_name_override = w_cfg.get("display_text", "")
        use_24h = d_cfg.get("use_24h_format", False)

        # Resolve dark mode
        target_mode = dark_mode
        if target_mode is None:
            target_mode = d_cfg.get("dark_mode", False)

        if isinstance(target_mode, bool):
            is_dark = target_mode
        elif isinstance(target_mode, (int, float)):
            is_dark = (target_mode == 1)
        elif isinstance(target_mode, str):
            s = target_mode.strip().lower()
            if s in ("on", "true", "yes", "1", "dark"):
                is_dark = True
            elif s in ("auto", "solar", "automatic"):
                is_dark = self._evaluate_solar_dark_mode(current_data)
            else:
                is_dark = False
        else:
            is_dark = False

        # Resolve layout style
        resolved_style = layout_style
        if resolved_style is None:
            resolved_style = d_cfg.get("layout_style", "classic")
        resolved_style = normalize_layout_style(resolved_style)

        # Resolve hero size
        resolved_size = hero_size
        if resolved_size is None:
            resolved_size = d_cfg.get("hero_size", "standard")
        resolved_size = normalize_hero_size(resolved_size)

        # Prepare parsed data dictionary
        data = self._prepare_data(
            forecast_data=forecast_data,
            current_data=current_data,
            kcno_obs=kcno_obs,
            use_metric=use_metric,
            display_name_override=display_name_override,
            use_24h=use_24h
        )

        if resolved_style == "widgets":
            img = self._render_widgets(data, is_dark, resolved_size, alert_text, aqi_text, freshness_text)
        elif resolved_style == "dualtone":
            img = self._render_dualtone(data, is_dark, resolved_size, alert_text, aqi_text, freshness_text)
        elif resolved_style == "minimalist":
            img = self._render_minimalist(data, is_dark, resolved_size, alert_text, aqi_text, freshness_text)
        else:
            img = self._render_classic(data, is_dark, resolved_size, alert_text, aqi_text, freshness_text)

        self.current_image = img
        return img

    def get_current_png_bytes(self) -> Optional[bytes]:
        """Returns PNG byte array of the current render for the web preview mirror."""
        if self.current_image is None:
            return None
        buf = io.BytesIO()
        self.current_image.save(buf, format="PNG")
        return buf.getvalue()

_renderer_instance = None
_renderer_lock = threading.RLock()

def get_renderer():
    global _renderer_instance
    with _renderer_lock:
        if _renderer_instance is None:
            _renderer_instance = WeatherRenderer()
        return _renderer_instance

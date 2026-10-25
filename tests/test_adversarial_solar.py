#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adversarial Stress Test Suite for Milestone 2:
Dark Mode, Solar Auto-Switching, Binarization Symmetry, and Input Resilience.

Authored by: m2_challenger_2 (teamwork_preview_challenger)
"""

import os
import sys
import json
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from display.renderer import WeatherRenderer, to_sharp_1bit, get_renderer
from display.epaper import EPaperDisplay
from services.scheduler import evaluate_dark_mode, calculate_astronomical_solar
from config.settings import normalize_dark_mode


class TestBinarizationAndStrokeSymmetry(unittest.TestCase):
    """Empirically test stroke thinning elimination and contrast preservation."""

    @classmethod
    def setUpClass(cls):
        cls.renderer = get_renderer()
        cache_path = BASE_DIR / "weather_cache.json"
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cls.current_data = data.get("current", {})
            cls.forecast_data = data.get("forecast", {"list": []})
        else:
            cls.current_data = {
                "coord": {"lat": 33.98, "lon": -117.56},
                "main": {"temp": 295.15, "humidity": 50},
                "wind": {"speed": 3.0},
                "weather": [{"icon": "01d", "main": "Clear"}],
                "sys": {"sunrise": 1726320600, "sunset": 1726367400},
                "timezone": -25200,
                "name": "Eastvale"
            }
            cls.forecast_data = {"list": []}

    def test_stroke_preservation_full_render(self):
        """Empirically compare foreground pixel counts: T=150 light vs T=105 dark vs T=150 naive dark."""
        img_l = self.renderer.render(self.forecast_data, self.current_data, dark_mode=False, aqi_text="AQI: Good")
        img_d = self.renderer.render(self.forecast_data, self.current_data, dark_mode=True, aqi_text="AQI: Good")

        bit_l = to_sharp_1bit(img_l, threshold=150)
        bit_d_sym = to_sharp_1bit(img_d, threshold=105)
        bit_d_naive = to_sharp_1bit(img_d, threshold=150)

        arr_l = np.array(bit_l)
        arr_d_sym = np.array(bit_d_sym)
        arr_d_naive = np.array(bit_d_naive)

        fg_l = int(np.sum(arr_l == False))        # 0 is black ink in light mode
        fg_d_sym = int(np.sum(arr_d_sym == True)) # 255 is white ink in dark mode
        fg_d_naive = int(np.sum(arr_d_naive == True))

        # Naive threshold 150 must exhibit severe glyph erosion (>1,000 pixels lost)
        pixels_lost = fg_l - fg_d_naive
        self.assertGreater(pixels_lost, 1000,
                           f"Naive dark threshold 150 should suffer severe stroke thinning (>1000px lost), got {pixels_lost}")

        # Symmetrical threshold 105 must preserve stroke weight within 0.5%
        sym_diff = abs(fg_d_sym - fg_l)
        sym_pct = (sym_diff / float(fg_l)) * 100.0
        self.assertLess(sym_pct, 0.5,
                        f"Symmetrical threshold 105 variance must be < 0.5%, got {sym_pct:.3f}% ({sym_diff}px diff)")

    def test_auto_polarity_threshold_inference(self):
        """Verify to_sharp_1bit automatically infers threshold from canvas corner."""
        img_l = self.renderer.render(self.forecast_data, self.current_data, dark_mode=False)
        img_d = self.renderer.render(self.forecast_data, self.current_data, dark_mode=True)

        auto_l = to_sharp_1bit(img_l)
        auto_d = to_sharp_1bit(img_d)

        explicit_l = to_sharp_1bit(img_l, threshold=150)
        explicit_d = to_sharp_1bit(img_d, threshold=105)

        self.assertEqual(np.sum(np.array(auto_l) != np.array(explicit_l)), 0,
                         "Auto-detection on light canvas did not match threshold 150!")
        self.assertEqual(np.sum(np.array(auto_d) != np.array(explicit_d)), 0,
                         "Auto-detection on dark canvas did not match threshold 105!")

    def test_rotation_commutativity_with_binarization(self):
        """Verify rotating 180 before or after to_sharp_1bit yields 0 pixel difference."""
        img_l = self.renderer.render(self.forecast_data, self.current_data, dark_mode=False)
        img_d = self.renderer.render(self.forecast_data, self.current_data, dark_mode=True)

        # Path 1: rotate then binarize (hardware path)
        rot_bin_l = to_sharp_1bit(img_l.rotate(180))
        rot_bin_d = to_sharp_1bit(img_d.rotate(180))

        # Path 2: binarize then rotate
        bin_rot_l = to_sharp_1bit(img_l).rotate(180)
        bin_rot_d = to_sharp_1bit(img_d).rotate(180)

        self.assertEqual(int(np.sum(np.array(rot_bin_l) != np.array(bin_rot_l))), 0,
                         "Rotation commutative failure in light mode!")
        self.assertEqual(int(np.sum(np.array(rot_bin_d) != np.array(bin_rot_d))), 0,
                         "Rotation commutative failure in dark mode!")


class TestLayoutCoordinateStability(unittest.TestCase):
    """Verify all 11 refined layout coordinates remain intact with zero spatial drift."""

    @classmethod
    def setUpClass(cls):
        cls.renderer = get_renderer()
        cache_path = BASE_DIR / "weather_cache.json"
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cls.current_data = data.get("current", {})
            cls.forecast_data = data.get("forecast", {"list": []})
        else:
            cls.current_data = {
                "coord": {"lat": 33.98, "lon": -117.56},
                "main": {"temp": 295.15, "humidity": 50},
                "wind": {"speed": 3.0},
                "weather": [{"icon": "01d", "main": "Clear"}],
                "sys": {"sunrise": 1726320600, "sunset": 1726367400},
                "timezone": -25200,
                "name": "Eastvale"
            }
            cls.forecast_data = {"list": []}

    def test_canvas_dimensions_and_card_margins(self):
        """Verify canvas is strictly 800x480 and outer margins are preserved."""
        img_l = self.renderer.render(self.forecast_data, self.current_data, dark_mode=False)
        self.assertEqual(img_l.size, (800, 480))

        arr = np.array(to_sharp_1bit(img_l, threshold=150))
        # Top margin: rows 0..15 must be 0 ink
        self.assertEqual(int(np.sum(arr[0:16, :] == False)), 0, "Top margin [0..15] has leaked ink!")
        # Bottom margin: rows 469..479 must be 0 ink
        self.assertEqual(int(np.sum(arr[469:480, :] == False)), 0, "Bottom margin [469..479] has leaked ink!")
        # Left margin: cols 0..19 must be 0 ink
        self.assertEqual(int(np.sum(arr[:, 0:20] == False)), 0, "Left margin [0..19] has leaked ink!")
        # Right margin: cols 781..799 must be 0 ink
        self.assertEqual(int(np.sum(arr[:, 781:800] == False)), 0, "Right margin [781..799] has leaked ink!")


class TestRendererDarkModeInputResilience(unittest.TestCase):
    """
    Adversarially stress test WeatherRenderer.render with non-standard values of dark_mode:
    'OFF', 'off', '  on  ', 'AUTO', True, False, 1, 0, None, invalid strings.
    """

    @classmethod
    def setUpClass(cls):
        cls.renderer = get_renderer()
        cache_path = BASE_DIR / "weather_cache.json"
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cls.current_data = data.get("current", {})
            cls.forecast_data = data.get("forecast", {"list": []})
        else:
            cls.current_data = {
                "coord": {"lat": 33.98, "lon": -117.56},
                "main": {"temp": 295.15, "humidity": 50},
                "wind": {"speed": 3.0},
                "weather": [{"icon": "01d", "main": "Clear"}],
                "sys": {"sunrise": 0, "sunset": 86400},
                "timezone": -25200,
                "name": "Eastvale"
            }
            cls.forecast_data = {"list": []}

    def _get_hero_icon_corner_pixel(self, img: Image.Image) -> int:
        """Helper to inspect the top-left corner pixel of the pasted hero weather icon."""
        arr = np.array(img)
        card_y0 = 154
        card_cx = 20 + 135
        s_hero_x = card_cx - 70 // 2
        return int(arr[card_y0 + 74, s_hero_x])

    def test_render_string_off_equals_boolean_false(self):
        """Stress test: dark_mode='off' MUST render identically to dark_mode=False with 0 pixel difference."""
        img_off = self.renderer.render(self.forecast_data, self.current_data, dark_mode="off")
        img_false = self.renderer.render(self.forecast_data, self.current_data, dark_mode=False)

        diff = int(np.sum(np.array(img_off) != np.array(img_false)))
        self.assertEqual(diff, 0,
                         f"dark_mode='off' corrupted {diff} pixels compared to dark_mode=False! "
                         f"(Check if load_weather_icon received 'off' string instead of boolean is_dark)")

    def test_render_string_OFF_uppercase(self):
        """Stress test: dark_mode='OFF' must not invert weather icon backgrounds."""
        img = self.renderer.render(self.forecast_data, self.current_data, dark_mode="OFF")
        arr = np.array(img)
        canvas_bg = int(arr[0, 0])
        hero_bg = self._get_hero_icon_corner_pixel(img)
        self.assertEqual(canvas_bg, 255, "Canvas background must be 255 for 'OFF'")
        self.assertEqual(hero_bg, 255,
                         f"Hero icon background was {hero_bg} instead of 255 when dark_mode='OFF'!")

    def test_render_whitespace_on(self):
        """Stress test: dark_mode='  on  ' must render dark mode with black canvas and black icon background."""
        img = self.renderer.render(self.forecast_data, self.current_data, dark_mode="  on  ")
        arr = np.array(img)
        canvas_bg = int(arr[0, 0])
        hero_bg = self._get_hero_icon_corner_pixel(img)
        self.assertEqual(canvas_bg, 0, "Canvas background must be 0 for '  on  '")
        self.assertEqual(hero_bg, 0,
                         f"Hero icon background was {hero_bg} instead of 0 when dark_mode='  on  '!")

    def test_render_string_auto_daytime(self):
        """Stress test: dark_mode='AUTO' during daylight must render light mode without black icon box."""
        now_ts = int(datetime.now(timezone.utc).timestamp())
        day_current = dict(self.current_data)
        day_current["sys"] = {"sunrise": now_ts - 3600, "sunset": now_ts + 3600}
        img = self.renderer.render(self.forecast_data, day_current, dark_mode="AUTO")
        arr = np.array(img)
        canvas_bg = int(arr[0, 0])
        hero_bg = self._get_hero_icon_corner_pixel(img)
        self.assertEqual(canvas_bg, 255, "Canvas background must be 255 for daytime AUTO")
        self.assertEqual(hero_bg, 255,
                         f"Hero icon background was {hero_bg} instead of 255 when dark_mode='AUTO' during daytime!")

    def test_render_settings_dark_mode_on_with_none_argument(self):
        """
        Stress test: When dark_mode=None is passed (default) and settings={'display': {'dark_mode': 'on'}},
        the rendered dashboard must have dark icons without white boxes (identical to dark_mode=True).
        """
        dark_cfg = {"display": {"dark_mode": "on"}}
        img_cfg = self.renderer.render(self.forecast_data, self.current_data, settings=dark_cfg, dark_mode=None)
        img_explicit = self.renderer.render(self.forecast_data, self.current_data, dark_mode=True)

        diff = int(np.sum(np.array(img_cfg) != np.array(img_explicit)))
        self.assertEqual(diff, 0,
                         f"Settings dark_mode='on' corrupted {diff} pixels compared to explicit dark_mode=True! "
                         f"(Check if load_weather_icon received None instead of is_dark=True)")

    def test_render_numeric_inputs_1_and_0(self):
        """Stress test: numeric 1 (dark) and 0 (light) must resolve cleanly."""
        img_1 = self.renderer.render(self.forecast_data, self.current_data, dark_mode=1)
        img_0 = self.renderer.render(self.forecast_data, self.current_data, dark_mode=0)

        self.assertEqual(int(np.array(img_1)[0, 0]), 0)
        self.assertEqual(self._get_hero_icon_corner_pixel(img_1), 0)

        self.assertEqual(int(np.array(img_0)[0, 0]), 255)
        self.assertEqual(self._get_hero_icon_corner_pixel(img_0), 255)

    def test_render_invalid_string_fallback_to_light(self):
        """Stress test: invalid string 'invalid_theme' must fall back to light mode with white icon background."""
        img = self.renderer.render(self.forecast_data, self.current_data, dark_mode="invalid_theme")
        arr = np.array(img)
        canvas_bg = int(arr[0, 0])
        hero_bg = self._get_hero_icon_corner_pixel(img)
        self.assertEqual(canvas_bg, 255)
        self.assertEqual(hero_bg, 255,
                         f"Invalid string caused hero icon background to be {hero_bg} instead of 255!")


class TestExtremeGeographicalCoordinates(unittest.TestCase):
    """
    Test extreme geographic latitudes, specifically the North Pole (+90.0)
    and South Pole (-90.0), ensuring the polar singularity denom=0 is handled
    correctly and returns Polar Night (None, None) / Midnight Sun (-1.0, -1.0).
    """

    def test_north_pole_polar_night_and_day(self):
        # North Pole in deep winter (Dec 21) -> Polar night (sun never rises)
        dt_winter = datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc)
        sr, ss = calculate_astronomical_solar(90.0, 0.0, dt=dt_winter, tz_offset_seconds=0)
        self.assertIsNone(sr, "North Pole in winter solstice must return None for sunrise (polar night)")
        self.assertIsNone(ss, "North Pole in winter solstice must return None for sunset (polar night)")
        self.assertTrue(evaluate_dark_mode("auto", None, 90.0, 0.0, current_time=dt_winter),
                        "North Pole in winter solstice must be dark mode")

        # North Pole in summer solstice (June 21) -> Polar day / Midnight Sun (sun never sets)
        dt_summer = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        sr_s, ss_s = calculate_astronomical_solar(90.0, 0.0, dt=dt_summer, tz_offset_seconds=0)
        self.assertEqual(sr_s, -1.0, "North Pole in summer solstice must return -1.0 (polar day)")
        self.assertEqual(ss_s, -1.0, "North Pole in summer solstice must return -1.0 (polar day)")
        self.assertFalse(evaluate_dark_mode("auto", None, 90.0, 0.0, current_time=dt_summer),
                         "North Pole in summer solstice must be light mode")

    def test_south_pole_polar_night_and_day(self):
        # South Pole in winter (June 21) -> Polar night (sun never rises)
        dt_winter = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        sr, ss = calculate_astronomical_solar(-90.0, 0.0, dt=dt_winter, tz_offset_seconds=0)
        self.assertIsNone(sr, "South Pole in June solstice must return None for sunrise (polar night)")
        self.assertIsNone(ss, "South Pole in June solstice must return None for sunset (polar night)")
        self.assertTrue(evaluate_dark_mode("auto", None, -90.0, 0.0, current_time=dt_winter),
                        "South Pole in June solstice must be dark mode")

        # South Pole in summer (Dec 21) -> Polar day / Midnight Sun (sun never sets)
        dt_summer = datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc)
        sr_s, ss_s = calculate_astronomical_solar(-90.0, 0.0, dt=dt_summer, tz_offset_seconds=0)
        self.assertEqual(sr_s, -1.0, "South Pole in Dec solstice must return -1.0 (polar day)")
        self.assertEqual(ss_s, -1.0, "South Pole in Dec solstice must return -1.0 (polar day)")
        self.assertFalse(evaluate_dark_mode("auto", None, -90.0, 0.0, current_time=dt_summer),
                         "South Pole in Dec solstice must be light mode")


class TestCorruptedAndHostilePayloads(unittest.TestCase):
    """
    Stress-test evaluate_dark_mode and calculate_astronomical_solar with corrupted,
    hostile, or non-numeric structures in weather payload (coords, tz, timestamps).
    """

    def setUp(self):
        self.lat = 33.98
        self.lon = -117.56
        self.dt_noon = datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc)

    def test_type_corrupted_sys_data(self):
        corrupted_payloads = [
            {"coord": {"lat": "invalid", "lon": "invalid"}},
            {"coord": {"lat": None, "lon": None}},
            {"coord": "not_a_dict"},
            {"timezone": "invalid"},
            {"timezone": None},
            {"timezone": "3600"},
            {"timezone": 999999999999},
            {"sys": "not_a_dict"},
            {"sys": {"sunrise": "invalid", "sunset": "invalid"}},
            {"sys": {"sunrise": None, "sunset": None}},
            {"sys": {"sunrise": 0, "sunset": 0}},
        ]

        for payload in corrupted_payloads:
            try:
                res = evaluate_dark_mode("auto", payload, self.lat, self.lon, current_time=self.dt_noon)
                self.assertIsInstance(res, bool, f"Payload {payload} should return bool, got {type(res)}")
            except Exception as e:
                self.fail(f"Corrupted payload {payload} raised unhandled exception: {e}")


if __name__ == "__main__":
    unittest.main()

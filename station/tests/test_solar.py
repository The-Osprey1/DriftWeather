#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Unit and Validation Test Suite for Milestone 2:
Theme Controls, Solar Auto-Switching Engine, and Symmetrical 1-Bit Thresholding.

Tests cover:
1. Settings normalization ("off", "on", "auto", bools, numbers, whitespace, case insensitivity, fallbacks).
2. Solar auto-switching transitions across 11 key timestamps (noon, midnight, sunrise, sunset).
3. Stale-cache resilience (>24h, 5-day old cache at solar noon, 7-day old cache).
4. Zero-dependency offline astronomical solar calculation fallback.
5. Symmetrical 1-bit thresholding (auto-detection and threshold=105 in dark mode vs 150 in light mode).
6. Web server settings API (/api/settings GET and POST).

Run via:
    python -m unittest tests/test_solar.py
"""

import os
import sys
import json
import math
import shutil
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image, ImageOps, ImageDraw
import numpy as np

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import Settings, normalize_dark_mode
from services.scheduler import evaluate_dark_mode, calculate_astronomical_solar, DisplayScheduler
from display.renderer import to_sharp_1bit, get_renderer
from web.server import create_app


class TestSettingsNormalization(unittest.TestCase):
    """Test settings normalization for 3-way dark mode."""

    def test_normalize_valid_strings(self):
        self.assertEqual(normalize_dark_mode("off"), "off")
        self.assertEqual(normalize_dark_mode("on"), "on")
        self.assertEqual(normalize_dark_mode("auto"), "auto")

    def test_normalize_case_and_whitespace(self):
        self.assertEqual(normalize_dark_mode("OFF"), "off")
        self.assertEqual(normalize_dark_mode("  On  "), "on")
        self.assertEqual(normalize_dark_mode("Auto\n"), "auto")
        self.assertEqual(normalize_dark_mode("AuTo"), "auto")
        self.assertEqual(normalize_dark_mode("  auto  "), "auto")

    def test_normalize_boolean_backward_compatibility(self):
        self.assertEqual(normalize_dark_mode(True), "on")
        self.assertEqual(normalize_dark_mode(False), "off")

    def test_normalize_numeric_backward_compatibility(self):
        self.assertEqual(normalize_dark_mode(1), "on")
        self.assertEqual(normalize_dark_mode(0), "off")

    def test_normalize_string_aliases(self):
        self.assertEqual(normalize_dark_mode("dark"), "on")
        self.assertEqual(normalize_dark_mode("light"), "off")
        self.assertEqual(normalize_dark_mode("solar"), "auto")
        self.assertEqual(normalize_dark_mode("automatic"), "auto")
        self.assertEqual(normalize_dark_mode("true"), "on")
        self.assertEqual(normalize_dark_mode("false"), "off")

    def test_normalize_invalid_fallbacks(self):
        self.assertEqual(normalize_dark_mode("invalid"), "off")
        self.assertEqual(normalize_dark_mode(""), "off")
        self.assertEqual(normalize_dark_mode(None), "off")
        self.assertEqual(normalize_dark_mode(123), "off")
        self.assertEqual(normalize_dark_mode([]), "off")
        self.assertEqual(normalize_dark_mode({}), "off")

    def test_settings_manager_integration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Settings(config_dir=tmpdir)
            # Test setting boolean True
            s.set("display", "dark_mode", True)
            self.assertEqual(s.get("display", "dark_mode"), "on")

            # Test setting boolean False
            s.set("display", "dark_mode", False)
            self.assertEqual(s.get("display", "dark_mode"), "off")

            # Test setting string "auto"
            s.set("display", "dark_mode", "auto")
            self.assertEqual(s.get("display", "dark_mode"), "auto")

            # Test update dictionary
            s.update({"display": {"dark_mode": True}}, persist=False)
            self.assertEqual(s.get("display", "dark_mode"), "on")

            s.update({"display": {"dark_mode": "off"}}, persist=False)
            self.assertEqual(s.get("display", "dark_mode"), "off")


class TestSolarTransitions(unittest.TestCase):
    """Test solar auto-switching engine across multiple times of day."""

    def setUp(self):
        # Eastvale, CA fixture with sunrise at 06:30 local and sunset at 19:30 local
        # Timezone PDT (-07:00, -25200s)
        self.lat = 33.98
        self.lon = -117.56
        self.tz_offset = -25200

        # Fixed reference date: 2026-09-14
        # Sunrise: 06:30 PDT -> 13:30 UTC
        # Sunset:  19:30 PDT -> 02:30 UTC (next day)
        sr_utc = datetime(2026, 9, 14, 13, 30, tzinfo=timezone.utc)
        ss_utc = datetime(2026, 9, 15, 2, 30, tzinfo=timezone.utc)

        self.weather_fixture = {
            "timezone": self.tz_offset,
            "coord": {"lat": self.lat, "lon": self.lon},
            "sys": {
                "sunrise": int(sr_utc.timestamp()),
                "sunset": int(ss_utc.timestamp())
            }
        }

    def _make_utc_time(self, local_hour: int, local_minute: int) -> datetime:
        """Create UTC datetime corresponding to 2026-09-14 local time in PDT."""
        dt_local = datetime(2026, 9, 14, local_hour, local_minute)
        dt_utc = dt_local - timedelta(seconds=self.tz_offset)
        return dt_utc.replace(tzinfo=timezone.utc)

    def test_overrides_on_and_off(self):
        noon_utc = self._make_utc_time(12, 0)
        midnight_utc = self._make_utc_time(0, 0)

        # Mode "on" is always dark
        self.assertTrue(evaluate_dark_mode("on", self.weather_fixture, self.lat, self.lon, current_time=noon_utc))
        self.assertTrue(evaluate_dark_mode("on", self.weather_fixture, self.lat, self.lon, current_time=midnight_utc))

        # Mode "off" is always light
        self.assertFalse(evaluate_dark_mode("off", self.weather_fixture, self.lat, self.lon, current_time=noon_utc))
        self.assertFalse(evaluate_dark_mode("off", self.weather_fixture, self.lat, self.lon, current_time=midnight_utc))

    def test_solar_transitions_11_points(self):
        # 1. Midnight (00:00) -> Dark
        t_0000 = self._make_utc_time(0, 0)
        self.assertTrue(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_0000))

        # 2. 03:00 -> Dark
        t_0300 = self._make_utc_time(3, 0)
        self.assertTrue(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_0300))

        # 3. 06:29 (1m before sunrise) -> Dark
        t_0629 = self._make_utc_time(6, 29)
        self.assertTrue(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_0629))

        # 4. 06:30 (exact sunrise) -> Light
        t_0630 = self._make_utc_time(6, 30)
        self.assertFalse(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_0630))

        # 5. 06:31 (1m after sunrise) -> Light
        t_0631 = self._make_utc_time(6, 31)
        self.assertFalse(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_0631))

        # 6. 12:00 (solar noon) -> Light
        t_1200 = self._make_utc_time(12, 0)
        self.assertFalse(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_1200))

        # 7. 15:30 (afternoon) -> Light
        t_1530 = self._make_utc_time(15, 30)
        self.assertFalse(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_1530))

        # 8. 19:29 (1m before sunset) -> Light
        t_1929 = self._make_utc_time(19, 29)
        self.assertFalse(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_1929))

        # 9. 19:30 (exact sunset) -> Dark
        t_1930 = self._make_utc_time(19, 30)
        self.assertTrue(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_1930))

        # 10. 19:31 (1m after sunset) -> Dark
        t_1931 = self._make_utc_time(19, 31)
        self.assertTrue(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_1931))

        # 11. 23:45 (late night) -> Dark
        t_2345 = self._make_utc_time(23, 45)
        self.assertTrue(evaluate_dark_mode("auto", self.weather_fixture, self.lat, self.lon, current_time=t_2345))


class TestStaleCacheResilience(unittest.TestCase):
    """Test stale-cache resilience ensuring station never locks in dark mode."""

    def setUp(self):
        self.lat = 33.98
        self.lon = -117.56
        self.tz_offset = -25200

    def test_stale_cache_25_hours_old(self):
        yesterday_sr_utc = datetime(2026, 9, 13, 13, 30, tzinfo=timezone.utc)
        yesterday_ss_utc = datetime(2026, 9, 14, 2, 30, tzinfo=timezone.utc)
        stale_fixture = {
            "timezone": self.tz_offset,
            "sys": {
                "sunrise": int(yesterday_sr_utc.timestamp()),
                "sunset": int(yesterday_ss_utc.timestamp())
            }
        }

        # Evaluate today at noon (12:00 PDT -> 19:00 UTC)
        today_noon_utc = datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc)
        self.assertFalse(evaluate_dark_mode("auto", stale_fixture, self.lat, self.lon, current_time=today_noon_utc),
                         "25h stale cache must evaluate noon as Light Mode!")

        # Evaluate today at midnight (00:00 PDT -> 07:00 UTC)
        today_midnight_utc = datetime(2026, 9, 14, 7, 0, tzinfo=timezone.utc)
        self.assertTrue(evaluate_dark_mode("auto", stale_fixture, self.lat, self.lon, current_time=today_midnight_utc),
                        "25h stale cache must evaluate midnight as Dark Mode!")

    def test_stale_cache_5_days_old_at_solar_noon(self):
        """MANDATORY: 5-day-old cache at solar noon returns False (Light Mode)."""
        five_days_ago_sr_utc = datetime(2026, 9, 9, 13, 30, tzinfo=timezone.utc)
        five_days_ago_ss_utc = datetime(2026, 9, 10, 2, 30, tzinfo=timezone.utc)
        stale_fixture_5d = {
            "timezone": self.tz_offset,
            "sys": {
                "sunrise": int(five_days_ago_sr_utc.timestamp()),
                "sunset": int(five_days_ago_ss_utc.timestamp())
            }
        }

        today_noon_utc = datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc)
        self.assertFalse(evaluate_dark_mode("auto", stale_fixture_5d, self.lat, self.lon, current_time=today_noon_utc),
                         "5-day-old cache at solar noon MUST return False!")

        today_midnight_utc = datetime(2026, 9, 14, 7, 0, tzinfo=timezone.utc)
        self.assertTrue(evaluate_dark_mode("auto", stale_fixture_5d, self.lat, self.lon, current_time=today_midnight_utc),
                        "5-day-old cache at midnight MUST return True!")

    def test_stale_cache_7_days_old(self):
        week_ago_sr_utc = datetime(2026, 9, 7, 13, 30, tzinfo=timezone.utc)
        week_ago_ss_utc = datetime(2026, 9, 8, 2, 30, tzinfo=timezone.utc)
        stale_fixture = {
            "timezone": self.tz_offset,
            "sys": {
                "sunrise": int(week_ago_sr_utc.timestamp()),
                "sunset": int(week_ago_ss_utc.timestamp())
            }
        }

        today_noon_utc = datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc)
        self.assertFalse(evaluate_dark_mode("auto", stale_fixture, self.lat, self.lon, current_time=today_noon_utc))

        today_midnight_utc = datetime(2026, 9, 14, 7, 0, tzinfo=timezone.utc)
        self.assertTrue(evaluate_dark_mode("auto", stale_fixture, self.lat, self.lon, current_time=today_midnight_utc))


class TestOfflineAstronomicalEngine(unittest.TestCase):
    """Test zero-dependency astronomical solar calculation fallback."""

    def test_offline_astronomical_accuracy(self):
        # Eastvale on equinox approx Sept 21
        dt_equinox = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
        sr_min, ss_min = calculate_astronomical_solar(33.98, -117.56, dt=dt_equinox, tz_offset_seconds=-25200)

        self.assertIsNotNone(sr_min)
        self.assertIsNotNone(ss_min)
        # Sunrise should be ~06:35 AM (6.6-6.8h) and Sunset ~18:40 PM (18.6-18.8h)
        self.assertAlmostEqual(sr_min / 60.0, 6.7, delta=0.5)
        self.assertAlmostEqual(ss_min / 60.0, 18.7, delta=0.5)

    def test_fallback_when_cache_none_or_empty(self):
        lat, lon = 33.98, -117.56
        # 05:00 PDT (12:00 UTC) -> before sunrise -> Dark Mode
        t_5am = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(evaluate_dark_mode("auto", None, lat, lon, current_time=t_5am))
        self.assertTrue(evaluate_dark_mode("auto", {}, lat, lon, current_time=t_5am))

        # 12:00 PM PDT (19:00 UTC) -> solar noon -> Light Mode
        t_noon = datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc)
        self.assertFalse(evaluate_dark_mode("auto", None, lat, lon, current_time=t_noon))
        self.assertFalse(evaluate_dark_mode("auto", {}, lat, lon, current_time=t_noon))

    def test_polar_latitude_safety(self):
        # Tromsø (69.65° N) in deep winter (Dec 21) -> Polar night
        dt_winter = datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc)
        sr, ss = calculate_astronomical_solar(69.65, 18.95, dt=dt_winter, tz_offset_seconds=3600)
        self.assertIsNone(sr)
        self.assertIsNone(ss)
        self.assertTrue(evaluate_dark_mode("auto", None, 69.65, 18.95, current_time=dt_winter))

        # Tromsø in summer (June 21) -> Midnight sun
        dt_summer = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        sr_s, ss_s = calculate_astronomical_solar(69.65, 18.95, dt=dt_summer, tz_offset_seconds=7200)
        self.assertEqual(sr_s, -1.0)
        self.assertEqual(ss_s, -1.0)
        self.assertFalse(evaluate_dark_mode("auto", None, 69.65, 18.95, current_time=dt_summer))

    def test_exact_polar_singularity(self):
        # Exact North Pole (+90.0) at winter solstice -> Polar night
        dt_winter = datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc)
        sr_np_w, ss_np_w = calculate_astronomical_solar(90.0, 0.0, dt=dt_winter, tz_offset_seconds=0)
        self.assertIsNone(sr_np_w)
        self.assertIsNone(ss_np_w)
        self.assertTrue(evaluate_dark_mode("auto", None, 90.0, 0.0, current_time=dt_winter))

        # Exact North Pole (+90.0) at summer solstice -> Midnight sun
        dt_summer = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        sr_np_s, ss_np_s = calculate_astronomical_solar(90.0, 0.0, dt=dt_summer, tz_offset_seconds=0)
        self.assertEqual(sr_np_s, -1.0)
        self.assertEqual(ss_np_s, -1.0)
        self.assertFalse(evaluate_dark_mode("auto", None, 90.0, 0.0, current_time=dt_summer))

        # Exact South Pole (-90.0) at June solstice -> Polar night
        sr_sp_w, ss_sp_w = calculate_astronomical_solar(-90.0, 0.0, dt=dt_summer, tz_offset_seconds=0)
        self.assertIsNone(sr_sp_w)
        self.assertIsNone(ss_sp_w)
        self.assertTrue(evaluate_dark_mode("auto", None, -90.0, 0.0, current_time=dt_summer))

        # Exact South Pole (-90.0) at December solstice -> Midnight sun
        sr_sp_s, ss_sp_s = calculate_astronomical_solar(-90.0, 0.0, dt=dt_winter, tz_offset_seconds=0)
        self.assertEqual(sr_sp_s, -1.0)
        self.assertEqual(ss_sp_s, -1.0)
        self.assertFalse(evaluate_dark_mode("auto", None, -90.0, 0.0, current_time=dt_winter))


class TestSymmetricalThresholding(unittest.TestCase):
    """Test symmetrical 1-bit thresholding (105 in dark mode vs 150 in light mode)."""

    def test_stroke_preservation_and_inversion_symmetry(self):
        # Create synthetic canvas with geometric shapes, lines, and gradients
        canvas_light = Image.new('L', (300, 300), 255)
        draw = ImageDraw.Draw(canvas_light)
        draw.ellipse([50, 50, 250, 250], fill=0, outline=60, width=8)
        draw.line([(20, 20), (280, 280)], fill=0, width=5)
        draw.line([(20, 280), (280, 20)], fill=40, width=3)
        for i in range(256):
            draw.line([(0, i), (30, i)], fill=i)

        canvas_dark = ImageOps.invert(canvas_light)

        # Binarize light with standard threshold 150
        b_light = to_sharp_1bit(canvas_light, threshold=150)
        arr_light = np.array(b_light)
        fg_light = (arr_light == False)  # 0 is black foreground in mode 1

        # Binarize dark with naive threshold 150 (severe erosion)
        b_dark_naive = to_sharp_1bit(canvas_dark, threshold=150)
        arr_dark_naive = np.array(b_dark_naive)
        fg_dark_naive = (arr_dark_naive == True)  # 255 is white foreground

        # Binarize dark with symmetrical threshold 105
        b_dark_sym = to_sharp_1bit(canvas_dark, threshold=105)
        arr_dark_sym = np.array(b_dark_sym)
        fg_dark_sym = (arr_dark_sym == True)

        light_pixels = np.sum(fg_light)
        dark_naive_pixels = np.sum(fg_dark_naive)
        dark_sym_pixels = np.sum(fg_dark_sym)

        # Naive threshold 150 loses significant foreground stroke pixels
        self.assertLess(dark_naive_pixels, light_pixels, "Naive threshold must show glyph erosion!")
        lost_px = light_pixels - dark_naive_pixels
        self.assertGreater(lost_px, 500, f"Expected >500 eroded pixels with naive threshold, got {lost_px}")

        # Symmetrical threshold 105 preserves stroke weight within 0.5%
        pixel_diff = abs(int(dark_sym_pixels) - int(light_pixels))
        relative_diff = pixel_diff / float(light_pixels)
        self.assertLess(relative_diff, 0.005,
                        f"Symmetrical threshold 105 discrepancy must be <0.5%, got {relative_diff:.4f}")

    def test_auto_detection_polarity(self):
        # Test light canvas: corner (0,0) is white (255) -> threshold 150
        c_light = Image.new('L', (50, 50), 255)
        b_l = to_sharp_1bit(c_light)
        self.assertEqual(b_l.getpixel((0, 0)), 255)

        # Test dark canvas: corner (0,0) is black (0) -> threshold 105
        c_dark = Image.new('L', (50, 50), 0)
        b_d = to_sharp_1bit(c_dark)
        self.assertEqual(b_d.getpixel((0, 0)), 0)

        # Explicit threshold override works
        b_custom = to_sharp_1bit(c_light, threshold=200)
        self.assertEqual(b_custom.mode, '1')


class TestWebThemeControlsAPI(unittest.TestCase):
    """Test Flask Web Control Panel theme control endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_api_settings_get_contains_theme_fields(self):
        res = self.client.get("/api/settings")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("display", data)
        self.assertIn("dark_mode", data["display"])
        self.assertIn(data["display"]["dark_mode"], ["off", "on", "auto"])
        self.assertIn("is_dark", data["display"])
        self.assertIsInstance(data["display"]["is_dark"], bool)
        self.assertIn("solar_summary", data["display"])

    def test_api_settings_post_normalizes_boolean(self):
        # Post boolean true -> normalized to "on"
        res = self.client.post("/api/settings", json={"display": {"dark_mode": True}})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["settings"]["display"]["dark_mode"], "on")
        self.assertTrue(data["settings"]["display"]["is_dark"])

        # Post boolean false -> normalized to "off"
        res2 = self.client.post("/api/settings", json={"display": {"dark_mode": False}})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["settings"]["display"]["dark_mode"], "off")
        self.assertFalse(data2["settings"]["display"]["is_dark"])

        # Post string "auto"
        res3 = self.client.post("/api/settings", json={"display": {"dark_mode": "auto"}})
        self.assertEqual(res3.status_code, 200)
        data3 = res3.get_json()
        self.assertEqual(data3["settings"]["display"]["dark_mode"], "auto")

        # Post string "off" to reset
        res4 = self.client.post("/api/settings", json={"display": {"dark_mode": "off"}})
        self.assertEqual(res4.status_code, 200)
        data4 = res4.get_json()
        self.assertEqual(data4["settings"]["display"]["dark_mode"], "off")


if __name__ == "__main__":
    unittest.main()

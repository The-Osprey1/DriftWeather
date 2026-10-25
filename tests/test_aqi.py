#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit and Regression Test Suite for Milestone 1: AQI Pipeline & Display.
Tests PIL badge rendering, pixel bounds containment, zero layout drift,
OpenWeather pollution fetcher mock scenarios, and cache retention fallback.
Run via: & "C:\\Users\\devyn\\anaconda3\\python.exe" -m unittest tests/test_aqi.py
"""

import os
import json
import tempfile
import unittest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

from display.renderer import WeatherRenderer, to_sharp_1bit
from weather.providers import WeatherProvider
from weather.cache import WeatherCache
from weather.updater import WeatherUpdater

BASE_DIR = Path(__file__).resolve().parent.parent


class TestAQIRenderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = WeatherRenderer(base_dir=BASE_DIR)
        cache_path = BASE_DIR / "weather_cache.json"
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cls.current_data = data.get("current", {})
            cls.forecast_data = data.get("forecast", {})
        else:
            cls.current_data = {
                "main": {"temp": 295.15, "humidity": 50},
                "wind": {"speed": 3.0},
                "weather": [{"icon": "01d", "main": "Clear"}]
            }
            cls.forecast_data = {"list": []}

    def test_unit_rendering_dimensions_and_mode(self):
        """Verify WeatherRenderer.render outputs valid 800x480 1-bit image."""
        img = self.renderer.render(self.forecast_data, self.current_data, aqi_text="AQI: Good")
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (800, 480))

        img_1bit = to_sharp_1bit(img, threshold=150)
        self.assertEqual(img_1bit.size, (800, 480))
        self.assertEqual(img_1bit.mode, "1")

    def test_pixel_bounds_containment_and_contrast(self):
        """Verify pill badge renders strictly at [676..764, 162..184] without clipping or bleed."""
        img = self.renderer.render(self.forecast_data, self.current_data, aqi_text="AQI: Good")
        img_1bit = to_sharp_1bit(img, threshold=150)
        arr = np.array(img_1bit)

        # Region coordinates
        x0, y0, x1, y1 = 676, 162, 764, 184
        badge = arr[y0:y1 + 1, x0:x1 + 1]

        # In mode '1': False is black (foreground outline/text), True is white (background)
        black_px = np.sum(badge == False)
        white_px = np.sum(badge == True)
        self.assertGreater(black_px, 150, "Pill outline and text black pixels missing")
        self.assertGreater(white_px, 1000, "Pill body white interior pixels missing")

        # Verify surrounding buffer margins remain pure white background (True)
        # Note: Card outline is at y=154..155 and card corner arc touches (162, 778)
        top_buf = arr[156:162, x0:x1 + 1]
        bot_buf = arr[185:195, x0:x1 + 1]
        left_buf = arr[y0:y1 + 1, 650:676]
        right_buf = arr[y0:y1 + 1, 765:778]

        self.assertTrue(np.all(top_buf == True), "Pixel bleed detected above pill badge")
        self.assertTrue(np.all(bot_buf == True), "Pixel bleed detected below pill badge")
        self.assertTrue(np.all(left_buf == True), "Pixel bleed detected left of pill badge")
        self.assertTrue(np.all(right_buf == True), "Pixel bleed detected right of pill badge")

    def test_coordinate_regression_zero_diff(self):
        """Confirm all 11 baseline layout coordinates are identical outside [676..764, 162..184]."""
        img_base = self.renderer.render(self.forecast_data, self.current_data, aqi_text=None)
        img_aqi = self.renderer.render(self.forecast_data, self.current_data, aqi_text="AQI: Good")

        arr_base = np.array(to_sharp_1bit(img_base, threshold=150))
        arr_aqi = np.array(to_sharp_1bit(img_aqi, threshold=150))

        # Mask out badge region
        mask = np.zeros_like(arr_base, dtype=bool)
        mask[162:185, 676:765] = True

        diff_outside = np.logical_xor(arr_base, arr_aqi) & (~mask)
        pixel_drift_count = int(np.sum(diff_outside))
        self.assertEqual(pixel_drift_count, 0, f"Regression failure: {pixel_drift_count} pixels drifted outside badge area!")

    def test_dark_mode_rendering_and_bounds(self):
        """Verify AQI badge renders cleanly in Dark Mode with zero drift outside badge."""
        dark_settings = {"display": {"dark_mode": True}}
        img_base = self.renderer.render(self.forecast_data, self.current_data, aqi_text=None, settings=dark_settings)
        img_aqi = self.renderer.render(self.forecast_data, self.current_data, aqi_text="AQI: Moderate", settings=dark_settings)

        arr_base = np.array(to_sharp_1bit(img_base, threshold=150))
        arr_aqi = np.array(to_sharp_1bit(img_aqi, threshold=150))

        # In dark mode: True is white (foreground), False is black (background)
        badge = arr_aqi[162:185, 676:765]
        white_px = np.sum(badge == True)
        self.assertGreater(white_px, 150, "Dark mode white outline/text pixels missing")

        mask = np.zeros_like(arr_base, dtype=bool)
        mask[162:185, 676:765] = True

        diff_outside = np.logical_xor(arr_base, arr_aqi) & (~mask)
        pixel_drift_count = int(np.sum(diff_outside))
        self.assertEqual(pixel_drift_count, 0, f"Dark mode regression: {pixel_drift_count} pixels drifted outside badge!")

    def test_normalization_and_clamping(self):
        """Verify delimiter stripping (•, ·) and text clamping prevent boundary overflow."""
        test_cases = [
            "AQI: Good \u2022 PM2.5: 10",
            "Good \u00b7 PM2.5: 5",
            "AQI: Moderate",
            "AQI: Very Poor",
            "AQI: Extremely Hazardous Conditions Exceeding Scale"
        ]
        for tc in test_cases:
            img = self.renderer.render(self.forecast_data, self.current_data, aqi_text=tc)
            arr = np.array(to_sharp_1bit(img, threshold=150))

            # Outside badge buffer margins must be clean
            top_buf = arr[156:162, 676:765]
            bot_buf = arr[185:195, 676:765]
            left_buf = arr[162:185, 650:676]
            right_buf = arr[162:185, 765:778]

            self.assertTrue(np.all(top_buf == True), f"Top margin bleed for '{tc}'")
            self.assertTrue(np.all(bot_buf == True), f"Bottom margin bleed for '{tc}'")
            self.assertTrue(np.all(left_buf == True), f"Left margin bleed for '{tc}'")
            self.assertTrue(np.all(right_buf == True), f"Right margin bleed for '{tc}'")

    def test_empty_and_whitespace_aqi(self):
        """Verify empty or whitespace-only aqi_text does not render badge."""
        img_base = self.renderer.render(self.forecast_data, self.current_data, aqi_text=None)
        arr_base = np.array(to_sharp_1bit(img_base, threshold=150))

        for empty_val in ["", "   ", None]:
            img_test = self.renderer.render(self.forecast_data, self.current_data, aqi_text=empty_val)
            arr_test = np.array(to_sharp_1bit(img_test, threshold=150))
            self.assertEqual(int(np.sum(np.logical_xor(arr_base, arr_test))), 0)


class TestAQIFetcher(unittest.TestCase):
    def setUp(self):
        self.provider = WeatherProvider(api_key="mock_test_key")

    @patch("requests.get")
    def test_fetch_aqi_success_200_all_indices(self, mock_get):
        """Verify fetch_aqi maps all 5 OpenWeather pollution indices to f'AQI: {label}'."""
        expected_mappings = {
            1: "AQI: Good",
            2: "AQI: Fair",
            3: "AQI: Moderate",
            4: "AQI: Poor",
            5: "AQI: Very Poor"
        }
        for idx, expected_str in expected_mappings.items():
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "list": [{
                    "main": {"aqi": idx},
                    "components": {"pm2_5": 8.5}
                }]
            }
            mock_get.return_value = mock_resp

            res = self.provider.fetch_aqi(33.963, -117.564)
            self.assertEqual(res, expected_str)

    @patch("requests.get")
    def test_fetch_aqi_network_timeout(self, mock_get):
        """Verify fetch_aqi gracefully handles connection timeouts without raising."""
        mock_get.side_effect = Exception("Connection timed out")
        res = self.provider.fetch_aqi(33.963, -117.564)
        self.assertIsNone(res)

    @patch("requests.get")
    def test_fetch_aqi_http_error_codes(self, mock_get):
        """Verify fetch_aqi returns None on HTTP 401, 429, 500 error responses."""
        for code in [401, 403, 429, 500, 503]:
            mock_resp = MagicMock()
            mock_resp.status_code = code
            mock_get.return_value = mock_resp
            res = self.provider.fetch_aqi(33.963, -117.564)
            self.assertIsNone(res, f"Expected None for HTTP {code}")

    @patch("requests.get")
    def test_fetch_aqi_empty_payload(self, mock_get):
        """Verify fetch_aqi handles empty list payload gracefully without IndexError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"list": []}
        mock_get.return_value = mock_resp

        res = self.provider.fetch_aqi(33.963, -117.564)
        self.assertIsNone(res)

    def test_fetch_aqi_missing_api_key(self):
        """Verify fetch_aqi returns None immediately if api_key is empty without network call."""
        provider = WeatherProvider(api_key="")
        res = provider.fetch_aqi(33.963, -117.564)
        self.assertIsNone(res)


class TestAQICache(unittest.TestCase):
    def test_cache_retention_when_incoming_aqi_is_none(self):
        """Verify WeatherCache retains existing cached AQI when updated with aqi=None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "weather_cache.json"
            cache = WeatherCache(cache_path=cache_file)

            # 1. Initial live save with valid AQI
            cache.save({"temp": 72}, {"list": []}, alert=None, aqi="AQI: Good", source="live")
            _, _, _, aqi1, _ = cache.get_data()
            self.assertEqual(aqi1, "AQI: Good")

            # 2. Subsequent live save when AQI fetch failed (aqi=None)
            cache.save({"temp": 74}, {"list": []}, alert=None, aqi=None, source="live")
            _, _, _, aqi2, _ = cache.get_data()
            self.assertEqual(aqi2, "AQI: Good", "Existing cached AQI was overwritten with None!")

    def test_cache_persistence_roundtrip(self):
        """Verify WeatherCache saves to disk and reloads AQI on fresh instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "weather_cache.json"
            cache = WeatherCache(cache_path=cache_file)
            cache.save({"temp": 68}, {"list": []}, alert=None, aqi="AQI: Moderate", source="live")

            # Re-read from disk
            reloaded = WeatherCache(cache_path=cache_file)
            _, _, _, aqi, _ = reloaded.get_data()
            self.assertEqual(aqi, "AQI: Moderate")

    def test_updater_fallback_retention(self):
        """Verify WeatherUpdater preserves cached AQI when provider.fetch_aqi returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "weather_cache.json"
            cache = WeatherCache(cache_path=cache_file)
            cache.save({"temp": 70}, {"list": []}, alert=None, aqi="AQI: Fair", source="live")

            updater = WeatherUpdater(cache=cache)

            # Mock provider where fetch_current and fetch_forecast succeed, but fetch_aqi returns None
            with patch("weather.updater.WeatherProvider") as MockProviderCls:
                mock_p = MagicMock()
                mock_p.fetch_current.return_value = {
                    "coord": {"lat": 33.963, "lon": -117.564},
                    "timezone": -25200,
                    "main": {"temp": 294.0, "humidity": 55},
                    "weather": [{"icon": "01d", "main": "Clear"}]
                }
                mock_p.fetch_forecast.return_value = {"list": []}
                mock_p.fetch_nws_alerts.return_value = None
                mock_p.fetch_aqi.return_value = None  # AQI API offline/timeout
                mock_p.fetch_kcno_observation.return_value = None
                MockProviderCls.return_value = mock_p

                success = updater.refresh_weather(is_online=True)
                self.assertTrue(success)

                # Confirm cache still holds 'AQI: Fair'
                _, _, _, aqi, _ = cache.get_data()
                self.assertEqual(aqi, "AQI: Fair")


if __name__ == "__main__":
    unittest.main()

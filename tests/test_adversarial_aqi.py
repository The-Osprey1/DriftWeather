#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Empirical Adversarial Verification Suite for Milestone 1 (AQI Pipeline & Display).
Stress-tests:
1. Pixel invariance (delta == 0 outside [676..764, 162..184]) across diverse weather conditions
   (Hot, Freezing, Rainy, Sunny, and live cache) in both Light Mode and Dark Mode.
2. Binary pixel validity in 1-bit mode: strictly {0, 255} with crisp contrast.
3. Dark Mode contrast: background is 0, text/outline is 255, surrounding buffer margins are 0.
4. Stress-testing boundary edge cases: empty, whitespace, ultra-long strings, unicode delimiters.
"""

import sys
import json
import unittest
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, timezone
from PIL import Image

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from display.renderer import WeatherRenderer, to_sharp_1bit

BADGE_X0 = 676
BADGE_Y0 = 162
BADGE_X1 = 764
BADGE_Y1 = 184


def generate_synthetic_weather(condition: str) -> tuple[dict, dict]:
    """Generates synthetic forecast and current weather datasets for stress testing."""
    now_utc = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
    base_ts = int(now_utc.timestamp())

    if condition == "hot":
        # 106°F (314.26 K), desert dry, high wind
        temp_k = 314.26
        humidity = 12
        wind_speed = 7.5
        icon = "01d"
        desc = "Extreme Heat"
        pop_base = 0.0
        rain_3h = 0.0
        hourly_temps_k = [312.0, 314.0, 316.0, 315.0, 313.0, 310.0, 308.0, 306.0]
    elif condition == "freezing":
        # 14°F (263.15 K), snow, freezing conditions
        temp_k = 263.15
        humidity = 88
        wind_speed = 6.0
        icon = "13d"
        desc = "Heavy Snow"
        pop_base = 0.85
        rain_3h = 5.0
        hourly_temps_k = [263.0, 262.0, 261.0, 260.0, 262.0, 264.0, 265.0, 263.0]
    elif condition == "rainy":
        # 48°F (282.04 K), pouring rain, 100% pop
        temp_k = 282.04
        humidity = 97
        wind_speed = 9.2
        icon = "10d"
        desc = "Heavy Rain"
        pop_base = 0.95
        rain_3h = 18.5
        hourly_temps_k = [281.0, 282.0, 282.5, 283.0, 282.0, 281.5, 280.0, 279.5]
    elif condition == "sunny":
        # 75°F (297.15 K), mild clear day
        temp_k = 297.15
        humidity = 45
        wind_speed = 3.2
        icon = "01d"
        desc = "Clear Sky"
        pop_base = 0.0
        rain_3h = 0.0
        hourly_temps_k = [295.0, 297.0, 298.0, 299.0, 297.0, 294.0, 292.0, 291.0]
    else:
        raise ValueError(f"Unknown condition: {condition}")

    current_data = {
        "coord": {"lon": -117.56, "lat": 33.98},
        "weather": [{"id": 800, "main": desc, "description": desc.lower(), "icon": icon}],
        "main": {
            "temp": temp_k,
            "feels_like": temp_k + 1.5,
            "temp_min": temp_k - 2.0,
            "temp_max": temp_k + 3.0,
            "humidity": humidity,
            "pressure": 1012,
        },
        "visibility": 10000,
        "wind": {"speed": wind_speed, "deg": 260},
        "clouds": {"all": 10 if condition != "sunny" else 0},
        "dt": base_ts,
        "sys": {
            "type": 1,
            "id": 1234,
            "country": "US",
            "sunrise": base_ts - 21600,
            "sunset": base_ts + 21600,
        },
        "timezone": -25200,
        "name": f"TestCity-{condition.capitalize()}",
    }

    # Generate 5-day / 40-step forecast
    forecast_list = []
    for step in range(40):
        step_dt = now_utc + timedelta(hours=step * 3)
        t_step = hourly_temps_k[step % len(hourly_temps_k)] + (step % 3)
        forecast_list.append({
            "dt": int(step_dt.timestamp()),
            "main": {
                "temp": t_step,
                "temp_min": t_step - 1.0,
                "temp_max": t_step + 1.0,
                "humidity": humidity,
            },
            "weather": [{"id": 800, "main": desc, "description": desc.lower(), "icon": icon}],
            "clouds": {"all": 10},
            "wind": {"speed": wind_speed, "deg": 260},
            "visibility": 10000,
            "pop": pop_base,
            "rain": {"3h": rain_3h} if rain_3h > 0 else {},
            "sys": {"pod": "d" if 6 <= step_dt.hour < 18 else "n"},
            "dt_txt": step_dt.strftime("%Y-%m-%d %H:%M:%S"),
        })

    forecast_data = {
        "cod": "200",
        "message": 0,
        "cnt": len(forecast_list),
        "list": forecast_list,
        "city": {
            "name": f"TestCity-{condition.capitalize()}",
            "coord": {"lat": 33.98, "lon": -117.56},
            "timezone": -25200,
        },
    }
    return forecast_data, current_data


class TestAdversarialAQIEmpirical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = WeatherRenderer(base_dir=PROJECT_ROOT)
        cls.conditions = ["hot", "freezing", "rainy", "sunny"]

        # Also load real cached data if available
        cls.datasets = {}
        for cond in cls.conditions:
            cls.datasets[cond] = generate_synthetic_weather(cond)

        cache_path = PROJECT_ROOT / "weather_cache.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_json = json.load(f)
                cls.datasets["cached_live"] = (cache_json["forecast"], cache_json["current"])
            except Exception:
                pass

        # Comprehensive set of AQI test payloads
        cls.aqi_variants = [
            "AQI: Good",
            "AQI: Fair",
            "AQI: Moderate",
            "AQI: Poor",
            "AQI: Very Poor",
            "AQI: 35",
            "AQI: 152",
            "AQI: 500",
            "AQI: Good \u2022 PM2.5: 8.5",
            "Moderate \u00b7 PM2.5: 35",
            "AQI: Hazardous",
            "AQI: Extremely Hazardous Conditions Exceeding Scale",
            "AQI: 0",
        ]

    def test_empirical_pixel_invariance_across_all_conditions(self):
        """
        Adversarial Test 1:
        Verify delta == 0 outside [676..764, 162..184] across ALL weather conditions,
        modes (Light & Dark), and AQI strings.
        """
        # Create exclusion mask for badge region [676..764, 162..184]
        # Coordinates in PIL are inclusive: x in [676, 764], y in [162, 184]
        badge_mask = np.zeros((480, 800), dtype=bool)
        badge_mask[BADGE_Y0:BADGE_Y1 + 1, BADGE_X0:BADGE_X1 + 1] = True
        outside_mask = ~badge_mask

        for dset_name, (f_data, c_data) in self.datasets.items():
            for dark_mode in [False, True]:
                mode_str = "Dark" if dark_mode else "Light"
                settings = {"display": {"dark_mode": dark_mode}}

                # Baseline render (without AQI)
                img_base_raw = self.renderer.render(f_data, c_data, aqi_text=None, settings=settings)
                arr_base_raw = np.array(img_base_raw)
                arr_base_1bit = np.array(to_sharp_1bit(img_base_raw, threshold=150))

                for aqi_str in self.aqi_variants:
                    with self.subTest(condition=dset_name, mode=mode_str, aqi=aqi_str):
                        img_aqi_raw = self.renderer.render(f_data, c_data, aqi_text=aqi_str, settings=settings)
                        arr_aqi_raw = np.array(img_aqi_raw)
                        arr_aqi_1bit = np.array(to_sharp_1bit(img_aqi_raw, threshold=150))

                        # 1. Check raw grayscale render outside badge
                        raw_diff_outside = (arr_base_raw != arr_aqi_raw) & outside_mask
                        raw_drift_count = int(np.sum(raw_diff_outside))
                        self.assertEqual(
                            raw_drift_count, 0,
                            f"RAW pixel drift: {raw_drift_count} pixels drifted outside badge for {dset_name}, {mode_str}, '{aqi_str}'"
                        )

                        # 2. Check 1-bit sharp binarized render outside badge
                        diff_outside = np.logical_xor(arr_base_1bit, arr_aqi_1bit) & outside_mask
                        drift_count = int(np.sum(diff_outside))
                        self.assertEqual(
                            drift_count, 0,
                            f"1-bit pixel drift: {drift_count} pixels drifted outside badge for {dset_name}, {mode_str}, '{aqi_str}'"
                        )

    def test_binary_pixel_validity_inside_capsule(self):
        """
        Adversarial Test 2:
        Pixel values inside badge capsule in 1-bit mode must be strictly binary {0, 255}
        with crisp contrast (sufficient count of both foreground and background pixels).
        """
        for dset_name, (f_data, c_data) in self.datasets.items():
            for dark_mode in [False, True]:
                mode_str = "Dark" if dark_mode else "Light"
                settings = {"display": {"dark_mode": dark_mode}}

                for aqi_str in ["AQI: Good", "AQI: Moderate", "AQI: Very Poor", "AQI: 120"]:
                    with self.subTest(condition=dset_name, mode=mode_str, aqi=aqi_str):
                        img_aqi = self.renderer.render(f_data, c_data, aqi_text=aqi_str, settings=settings)
                        img_1bit = to_sharp_1bit(img_aqi, threshold=150)

                        # Convert 1-bit image to 'L' to inspect numerical pixel byte values
                        arr_l = np.array(img_1bit.convert('L'))
                        badge_l = arr_l[BADGE_Y0:BADGE_Y1 + 1, BADGE_X0:BADGE_X1 + 1]

                        unique_vals = set(np.unique(badge_l))
                        self.assertTrue(
                            unique_vals.issubset({0, 255}),
                            f"Non-binary pixel values found inside capsule: {unique_vals}"
                        )

                        count_0 = int(np.sum(badge_l == 0))
                        count_255 = int(np.sum(badge_l == 255))
                        total_badge_px = badge_l.size  # (184-162+1) * (764-676+1) = 23 * 89 = 2047

                        self.assertEqual(count_0 + count_255, total_badge_px)

                        if dark_mode:
                            # Dark mode: background is 0, text/outline is 255
                            self.assertGreater(count_255, 120, f"Dark mode foreground (white) pixels too low: {count_255}")
                            self.assertGreater(count_0, 1000, f"Dark mode background (black) pixels too low: {count_0}")
                        else:
                            # Light mode: background is 255, text/outline is 0
                            self.assertGreater(count_0, 120, f"Light mode foreground (black) pixels too low: {count_0}")
                            self.assertGreater(count_255, 1000, f"Light mode background (white) pixels too low: {count_255}")

    def test_dark_mode_contrast_and_polarity(self):
        """
        Adversarial Test 3:
        In Dark Mode:
        - Badge capsule background is pure black (0).
        - Badge outline and text are pure white (255).
        - Immediate buffer margins around badge capsule are pure black (0).
        """
        dark_settings = {"display": {"dark_mode": True}}
        for dset_name, (f_data, c_data) in self.datasets.items():
            for aqi_str in ["AQI: Good", "AQI: Moderate", "AQI: Poor"]:
                with self.subTest(condition=dset_name, aqi=aqi_str):
                    img = self.renderer.render(f_data, c_data, aqi_text=aqi_str, settings=dark_settings)
                    img_1bit = to_sharp_1bit(img, threshold=150)
                    arr = np.array(img_1bit.convert('L'))

                    # Verify buffer margins around the badge are pure black (0) in dark mode
                    top_buf = arr[156:162, BADGE_X0:BADGE_X1 + 1]
                    bot_buf = arr[BADGE_Y1 + 1:BADGE_Y1 + 11, BADGE_X0:BADGE_X1 + 1]
                    left_buf = arr[BADGE_Y0:BADGE_Y1 + 1, 650:BADGE_X0]
                    right_buf = arr[BADGE_Y0:BADGE_Y1 + 1, BADGE_X1 + 1:778]

                    self.assertTrue(np.all(top_buf == 0), f"Dark mode top margin has non-zero pixels: {np.unique(top_buf)}")
                    self.assertTrue(np.all(bot_buf == 0), f"Dark mode bottom margin has non-zero pixels: {np.unique(bot_buf)}")
                    self.assertTrue(np.all(left_buf == 0), f"Dark mode left margin has non-zero pixels: {np.unique(left_buf)}")
                    self.assertTrue(np.all(right_buf == 0), f"Dark mode right margin has non-zero pixels: {np.unique(right_buf)}")

                    # Verify interior of capsule contains 0 (background) and 255 (text/outline)
                    badge = arr[BADGE_Y0:BADGE_Y1 + 1, BADGE_X0:BADGE_X1 + 1]
                    self.assertTrue(0 in badge, "Dark mode badge missing background 0")
                    self.assertTrue(255 in badge, "Dark mode badge missing foreground 255")

    def test_empty_and_whitespace_invariance(self):
        """
        Adversarial Test 4:
        Verify empty or whitespace-only aqi_text renders completely identical image
        to baseline (diff == 0 across ENTIRE 800x480 canvas).
        """
        for dset_name, (f_data, c_data) in self.datasets.items():
            for dark_mode in [False, True]:
                settings = {"display": {"dark_mode": dark_mode}}
                img_base = self.renderer.render(f_data, c_data, aqi_text=None, settings=settings)
                arr_base = np.array(to_sharp_1bit(img_base))

                for empty_val in ["", " ", "   \t\n  "]:
                    with self.subTest(condition=dset_name, dark=dark_mode, val=repr(empty_val)):
                        img_test = self.renderer.render(f_data, c_data, aqi_text=empty_val, settings=settings)
                        arr_test = np.array(to_sharp_1bit(img_test))
                        total_diff = int(np.sum(arr_base != arr_test))
                        self.assertEqual(total_diff, 0, f"Empty string {repr(empty_val)} caused {total_diff} diffs")

    def test_extreme_overflow_and_delimiter_stress(self):
        """
        Adversarial Test 5:
        Extreme strings with exotic delimiters, emoji, and huge lengths must not bleed outside badge.
        """
        extreme_cases = [
            "AQI: 9999999999999999999999999999999999999999",
            "AQI: Good \u2022 Extra Long Trailing Content That Should Be Stripped",
            "AQI: Moderate \u00b7 Another Trailing Delimiter Block",
            "   AQI:    Padded    Spaces   ",
            "AQI: !@#$%^&*()_+~`",
            "AQI",
            "AQI:",
        ]
        badge_mask = np.zeros((480, 800), dtype=bool)
        badge_mask[BADGE_Y0:BADGE_Y1 + 1, BADGE_X0:BADGE_X1 + 1] = True
        outside_mask = ~badge_mask

        f_data, c_data = self.datasets["sunny"]
        img_base = self.renderer.render(f_data, c_data, aqi_text=None)
        arr_base = np.array(to_sharp_1bit(img_base))

        for tc in extreme_cases:
            with self.subTest(case=tc):
                img_aqi = self.renderer.render(f_data, c_data, aqi_text=tc)
                arr_aqi = np.array(to_sharp_1bit(img_aqi))

                diff_outside = np.logical_xor(arr_base, arr_aqi) & outside_mask
                drift_count = int(np.sum(diff_outside))
                self.assertEqual(drift_count, 0, f"Extreme case '{tc}' caused {drift_count} pixels to bleed outside badge!")


def run_empirical_verification():
    """Runs verification directly with detailed reporting."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print("=" * 80)
    print("G4CAST EMPIRICAL ADVERSARIAL VERIFICATION SUITE -- MILESTONE 1 (AQI)")
    print("=" * 80)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAdversarialAQIEmpirical)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("=" * 80)
    if result.wasSuccessful():
        print("VERDICT: ALL ADVERSARIAL EMPIRICAL TESTS PASSED (100% SUCCESS)")
        return 0
    else:
        print(f"VERDICT: ADVERSARIAL TESTS FAILED ({len(result.failures)} failures, {len(result.errors)} errors)")
        return 1


if __name__ == "__main__":
    sys.exit(run_empirical_verification())

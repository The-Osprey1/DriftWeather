#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adversarial Stress Test Suite for Milestone 1: AQI Pipeline & Display.
Author: teamwork_preview_challenger (m1_challenger_1)

Tests:
1. Boundary inputs against WeatherRenderer.render(..., aqi_text=...):
   - Extremely long strings (1000 characters)
   - Unusual Unicode, emoji, control characters, empty strings, None
   - Unusual delimiters (•, ·, |, -, commas, ;, /)
2. Cache resilience under concurrent/rapid updates with intermittent None payloads.
3. Hostile/corrupted input robustness (non-string types, malformed cache payloads).
"""

import os
import sys
import json
import time
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np
from PIL import Image

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from display.renderer import WeatherRenderer, to_sharp_1bit
from weather.cache import WeatherCache
from weather.updater import WeatherUpdater

BADGE_X0 = 676
BADGE_Y0 = 162
BADGE_X1 = 764
BADGE_Y1 = 184


class TestAQIBoundaryInputs(unittest.TestCase):
    """Stress tests boundary inputs against WeatherRenderer.render(..., aqi_text=...)."""

    @classmethod
    def setUpClass(cls):
        cls.renderer = WeatherRenderer(base_dir=PROJECT_ROOT)
        cache_path = PROJECT_ROOT / "weather_cache.json"
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            cls.forecast_data = d["forecast"]
            cls.current_data = d["current"]
        else:
            cls.forecast_data = {"list": []}
            cls.current_data = {
                "main": {"temp": 295.15, "humidity": 50},
                "wind": {"speed": 3.0},
                "weather": [{"icon": "01d", "main": "Clear"}],
                "timezone": -25200,
                "name": "TestCity"
            }

        cls.base_img = cls.renderer.render(cls.forecast_data, cls.current_data, aqi_text=None)
        cls.base_arr = np.array(to_sharp_1bit(cls.base_img, threshold=150))

        cls.badge_mask = np.zeros_like(cls.base_arr, dtype=bool)
        cls.badge_mask[BADGE_Y0:BADGE_Y1 + 1, BADGE_X0:BADGE_X1 + 1] = True
        cls.outside_mask = ~cls.badge_mask

    def _check_pixel_drift(self, test_img: Image.Image, case_name: str) -> int:
        test_arr = np.array(to_sharp_1bit(test_img, threshold=150))
        diff_outside = np.logical_xor(self.base_arr, test_arr) & self.outside_mask
        drift_count = int(np.sum(diff_outside))
        return drift_count

    def test_extremely_long_string_1000_chars(self):
        """Stress-test: 1000 character string must not crash, must not bleed outside badge, and completes in bounded time."""
        long_str = "AQI: " + "X" * 1000
        t0 = time.time()
        img = self.renderer.render(self.forecast_data, self.current_data, aqi_text=long_str)
        elapsed = time.time() - t0

        drift = self._check_pixel_drift(img, "1000 chars")
        self.assertEqual(drift, 0, f"1000 chars caused {drift} pixels to bleed outside badge")
        self.assertLess(elapsed, 3.0, f"1000 chars render took excessive time: {elapsed:.2f}s")

    def test_empty_and_none_variants(self):
        """Stress-test: None, empty string, and whitespace-only strings render cleanly with 0 diff."""
        for val in [None, "", " ", "   \t\r\n   "]:
            with self.subTest(val=repr(val)):
                img = self.renderer.render(self.forecast_data, self.current_data, aqi_text=val)
                test_arr = np.array(to_sharp_1bit(img, threshold=150))
                diff_total = int(np.sum(self.base_arr != test_arr))
                self.assertEqual(diff_total, 0, f"Payload {repr(val)} altered canvas by {diff_total} pixels")

    def test_delimiters_containment(self):
        """Stress-test: Delimiters (•, ·, |, -, commas, ;, /) must not cause layout drift outside badge."""
        delimiters_to_test = [
            "AQI: Good \u2022 PM2.5: 10",
            "AQI: Fair \u00b7 PM2.5: 20",
            "AQI: Moderate | PM2.5: 35.0",
            "AQI: Poor - PM2.5: 65",
            "AQI: Very Poor, PM2.5: 150",
            "AQI: Good / PM2.5: 12",
            "AQI: Fair; PM2.5: 22",
            "AQI: 50 -> Moderate",
            "AQI: 42 -- Good"
        ]
        for s in delimiters_to_test:
            with self.subTest(case=s):
                img = self.renderer.render(self.forecast_data, self.current_data, aqi_text=s)
                drift = self._check_pixel_drift(img, s)
                self.assertEqual(drift, 0, f"Delimiter case '{s}' leaked {drift} pixels outside badge")

    def test_unicode_and_emojis(self):
        """Stress-test: Unicode scripts, emojis, and surrogates must render safely without bleed."""
        unicode_cases = [
            ("Smiley", "AQI: Good \U0001f600"),
            ("Mask", "AQI: \U0001f637 50"),
            ("Fire/Skull", "AQI: \U0001f525\U0001f480"),
            ("CJK", "AQI: \u826f\u597d (\u4f18)"),
            ("Cyrillic", "AQI: \u0425\u043e\u0440\u043e\u0448\u043e"),
            ("Arabic RTL", "AQI: \u0645\u0645\u062a\u0627\u0632"),
            ("Hebrew RTL", "AQI: \u05d8\u05d5\u05d1"),
            ("Devanagari", "AQI: \u0905\u091a\u094d\u091b\u093e"),
            ("Zalgo", "A\u0336Q\u0336I\u0336:\u0336 \u0336G\u0336o\u0336o\u0336d\u0336"),
            ("Combining", "AQI: e\u0301\u0302\u0303\u0304"),
            ("ZWSP/ZWJ", "AQI: Good\u200b\u200c\u200d\ufeff"),
            ("Surrogates", "AQI: \U00020000\U00020001"),
            ("Ligature", "AQI: \ufdfd"),
        ]
        for label, s in unicode_cases:
            with self.subTest(case=label):
                img = self.renderer.render(self.forecast_data, self.current_data, aqi_text=s)
                drift = self._check_pixel_drift(img, label)
                self.assertEqual(drift, 0, f"Unicode case '{label}' leaked {drift} pixels outside badge")

    def test_control_characters_and_newlines_containment(self):
        """
        Stress-test: Control characters and newlines must NOT leak pixels outside the badge capsule.
        CHALLENGER FAILURE FINDING: Multiline text in aqi_text causes PIL to render vertically outside the capsule.
        """
        ctrl_cases = [
            ("NUL", "AQI: \x00Good"),
            ("BEL/BS", "AQI: \x07\x08Good"),
            ("ESC", "AQI: \x1b[31mRed"),
            ("DEL", "AQI: Good\x7f"),
            ("Tabs", "AQI:\tGood\t50"),
            ("Newline", "AQI: Good\nBad"),
            ("Multi-Newline", "AQI: Good\nBad\r\nUgly"),
        ]
        for label, s in ctrl_cases:
            with self.subTest(case=label):
                img = self.renderer.render(self.forecast_data, self.current_data, aqi_text=s)
                drift = self._check_pixel_drift(img, label)
                self.assertEqual(
                    drift, 0,
                    f"VULNERABILITY DETECTED: Control/Newline case '{label}' leaked {drift} pixels outside badge area [676..764, 162..184]!"
                )


class TestAQIHostileAndCorruptedInputs(unittest.TestCase):
    """Stress tests non-string, corrupted, and malformed inputs against renderer and cache."""

    @classmethod
    def setUpClass(cls):
        cls.renderer = WeatherRenderer(base_dir=PROJECT_ROOT)
        cache_path = PROJECT_ROOT / "weather_cache.json"
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            cls.forecast_data = d["forecast"]
            cls.current_data = d["current"]
        else:
            cls.forecast_data = {"list": []}
            cls.current_data = {"main": {"temp": 295.15}, "weather": [{"icon": "01d"}]}

    def test_non_string_types_in_renderer(self):
        """
        Stress-test: Non-string types (int, float, dict, list, bool) passed as aqi_text
        must not crash WeatherRenderer.render with unhandled exceptions.
        CHALLENGER FAILURE FINDING: Crashes with AttributeError: 'int' object has no attribute 'strip'.
        """
        hostile_types = [
            (42, "integer 42"),
            (35.5, "float 35.5"),
            ({"aqi": 3}, "dict {'aqi': 3}"),
            (["AQI: Good"], "list ['AQI: Good']"),
            (True, "boolean True"),
            (b"AQI: Good", "bytes b'AQI: Good'"),
        ]
        for bad_val, label in hostile_types:
            with self.subTest(val=label):
                try:
                    img = self.renderer.render(self.forecast_data, self.current_data, aqi_text=bad_val)
                    self.assertIsInstance(img, Image.Image)
                except Exception as e:
                    self.fail(
                        f"CRASH VULNERABILITY DETECTED: WeatherRenderer.render crashed on hostile {label}: {type(e).__name__}: {e}"
                    )

    def test_corrupted_json_cache_load(self):
        """Stress-test: WeatherCache must handle corrupt/truncated JSON files without unhandled crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "weather_cache.json"

            # 1. Truncated JSON
            with open(cache_file, "w") as f:
                f.write('{"current": {"temp": 70}, "forecast": ')
            c = WeatherCache(cache_path=cache_file)
            curr, fore, alert, aqi, kcno = c.get_data()
            self.assertIsNone(curr)
            self.assertIsNone(aqi)

            # 2. Empty 0-byte file
            with open(cache_file, "w") as f:
                pass
            c2 = WeatherCache(cache_path=cache_file)
            curr2, fore2, alert2, aqi2, kcno2 = c2.get_data()
            self.assertIsNone(curr2)
            self.assertIsNone(aqi2)

            # 3. Binary garbage
            with open(cache_file, "wb") as f:
                f.write(b"\x00\xff\xfe\x01\x02\x03\x04\x05")
            c3 = WeatherCache(cache_path=cache_file)
            curr3, fore3, alert3, aqi3, kcno3 = c3.get_data()
            self.assertIsNone(curr3)
            self.assertIsNone(aqi3)


class TestAQICacheResilienceConcurrent(unittest.TestCase):
    """Stress tests WeatherCache under rapid concurrent updates with intermittent None payloads."""

    def test_concurrent_updates_with_intermittent_none(self):
        """
        Stress-test: 8 concurrent threads executing rapid save() calls with alternating
        valid AQI and None payloads.
        CHALLENGER FAILURE FINDING:
        - WeatherCache lacks file locking or thread synchronization.
        - Static .tmp collision causes [WinError 32] / [Errno 13] on Windows.
        - Failed saves result in lost updates.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "weather_cache.json"
            cache = WeatherCache(cache_path=cache_file)
            # Initialize with valid AQI
            init_ok = cache.save({"temp": 70}, {"list": []}, aqi="AQI: Baseline")
            self.assertTrue(init_ok)

            failed_saves: List[Tuple[int, int]] = []
            none_overwrites: List[Tuple[int, int]] = []

            def worker(tid: int):
                for i in range(25):
                    # Intermittent None payloads
                    val = None if (i % 2 == 1) else f"AQI: Thread-{tid}-{i}"
                    ok = cache.save({"temp": 70 + tid}, {"list": []}, aqi=val)
                    if not ok:
                        failed_saves.append((tid, i))
                    curr, fore, alert, aqi, kcno = cache.get_data()
                    if aqi is None:
                        none_overwrites.append((tid, i))
                    time.sleep(0.002)

            threads = [threading.Thread(target=worker, args=(t,)) for t in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(
                len(none_overwrites), 0,
                f"DATA LOSS VULNERABILITY: AQI was overwritten with None {len(none_overwrites)} times during concurrent saves!"
            )
            self.assertEqual(
                len(failed_saves), 0,
                f"RACE CONDITION VULNERABILITY: {len(failed_saves)} cache saves failed due to concurrent file collisions on Windows!"
            )

    def test_cache_retention_when_initial_cache_empty_and_aqi_is_none(self):
        """
        Stress-test: If WeatherCache is initialized without an active memory cache
        (or if load failed due to transient file lock), saving with aqi=None wipes existing on-disk AQI.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "weather_cache.json"
            c1 = WeatherCache(cache_path=cache_file)
            c1.save({"temp": 72}, {"list": []}, aqi="AQI: Good")

            # Simulate instance where load() failed (e.g. transient file lock or cold offline start)
            c2 = WeatherCache.__new__(WeatherCache)
            c2.cache_path = cache_file
            c2.last_fetch_time = 0.0
            c2.last_fetch_source = "cache"
            c2._cached_data = {}  # Empty in-memory state

            # c2 saves with aqi=None
            c2.save({"temp": 75}, {"list": []}, aqi=None)

            # Inspect disk
            c3 = WeatherCache(cache_path=cache_file)
            _, _, _, disk_aqi, _ = c3.get_data()

            self.assertIsNotNone(
                disk_aqi,
                "DATA LOSS VULNERABILITY: Cached AQI on disk was permanently wiped to null by an instance with empty in-memory state saving aqi=None!"
            )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    unittest.main()

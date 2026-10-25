#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite for multi-style and hero size customization in G4Cast.
Verifies normalization, rendering across all styles and sizes,
and persistence in settings manager.
"""

import unittest
import json
from pathlib import Path
from PIL import Image

from config.settings import Settings, normalize_layout_style, normalize_hero_size
from display.renderer import WeatherRenderer, to_sharp_1bit

class TestCustomizationStylesAndSizes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = Path(__file__).resolve().parent.parent
        cls.renderer = WeatherRenderer(base_dir=cls.base_dir)
        cache_file = cls.base_dir / "weather_cache.json"
        with open(cache_file, "r", encoding="utf-8") as f:
            d = json.load(f)
        cls.forecast = d["forecast"]
        cls.current = d["current"]

    def test_normalize_layout_style(self):
        """Test layout style normalizer handles valid styles, aliases, and bad inputs."""
        self.assertEqual(normalize_layout_style("classic"), "classic")
        self.assertEqual(normalize_layout_style("CLASSIC"), "classic")
        self.assertEqual(normalize_layout_style("default"), "classic")
        self.assertEqual(normalize_layout_style("widgets"), "widgets")
        self.assertEqual(normalize_layout_style("widget"), "widgets")
        self.assertEqual(normalize_layout_style("tiles"), "widgets")
        self.assertEqual(normalize_layout_style("dualtone"), "dualtone")
        self.assertEqual(normalize_layout_style("dual-tone"), "dualtone")
        self.assertEqual(normalize_layout_style("inverted"), "dualtone")
        self.assertEqual(normalize_layout_style("minimalist"), "minimalist")
        self.assertEqual(normalize_layout_style("minimal"), "minimalist")
        self.assertEqual(normalize_layout_style("unknown_style"), "classic")
        self.assertEqual(normalize_layout_style(None), "classic")

    def test_normalize_hero_size(self):
        """Test hero size normalizer handles valid sizes, aliases, and bad inputs."""
        self.assertEqual(normalize_hero_size("standard"), "standard")
        self.assertEqual(normalize_hero_size("STANDARD"), "standard")
        self.assertEqual(normalize_hero_size("normal"), "standard")
        self.assertEqual(normalize_hero_size("compact"), "compact")
        self.assertEqual(normalize_hero_size("small"), "compact")
        self.assertEqual(normalize_hero_size("dense"), "compact")
        self.assertEqual(normalize_hero_size("large"), "large")
        self.assertEqual(normalize_hero_size("huge"), "large")
        self.assertEqual(normalize_hero_size("glanceable"), "large")
        self.assertEqual(normalize_hero_size("huge_size"), "standard")
        self.assertEqual(normalize_hero_size(None), "standard")

    def test_render_all_styles_light_and_dark(self):
        """Verify all 4 layout styles render valid 800x480 images in light and dark mode."""
        styles = ["classic", "widgets", "dualtone", "minimalist"]
        for s in styles:
            for is_dark in [False, True]:
                with self.subTest(style=s, dark=is_dark):
                    img = self.renderer.render(
                        self.forecast, self.current,
                        layout_style=s,
                        dark_mode=is_dark,
                        aqi_text="AQI: Good"
                    )
                    self.assertIsInstance(img, Image.Image)
                    self.assertEqual(img.size, (800, 480))
                    self.assertEqual(img.mode, "L")
                    sharp = to_sharp_1bit(img, dark_mode=is_dark)
                    self.assertEqual(sharp.size, (800, 480))
                    self.assertEqual(sharp.mode, "1")

    def test_render_all_hero_sizes(self):
        """Verify all 3 hero sizes render valid images without errors."""
        sizes = ["compact", "standard", "large"]
        for sz in sizes:
            with self.subTest(hero_size=sz):
                img = self.renderer.render(
                    self.forecast, self.current,
                    hero_size=sz,
                    aqi_text="AQI: Moderate"
                )
                self.assertEqual(img.size, (800, 480))

    def test_settings_persistence_of_customization(self):
        """Verify settings manager normalizes and stores layout_style and hero_size."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            s = Settings(config_dir=tmppath)
            s.update({"display": {"layout_style": "WIDGETS", "hero_size": "LARGE"}}, persist=False)
            self.assertEqual(s.get("display", "layout_style"), "widgets")
            self.assertEqual(s.get("display", "hero_size"), "large")

            s.set("display", "layout_style", "dual-tone")
            s.set("display", "hero_size", "dense")
            self.assertEqual(s.get("display", "layout_style"), "dualtone")
            self.assertEqual(s.get("display", "hero_size"), "compact")

if __name__ == '__main__':
    unittest.main()

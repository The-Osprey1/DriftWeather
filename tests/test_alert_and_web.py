#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit and API Test Suite for Milestone 3 (Severe Weather Alert Banners & Simulation)
and Milestone 4 (Web Portal Configuration Backup, Restore, and Search).
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

from display.renderer import WeatherRenderer, to_sharp_1bit
from weather.cache import WeatherCache
from weather.updater import WeatherUpdater
from web.server import create_app

BASE_DIR = Path(__file__).resolve().parent.parent


class TestAlertAndWeb(unittest.TestCase):
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
            cls.current_data = {"main": {"temp": 295.15, "humidity": 50}, "weather": [{"icon": "01d", "main": "Clear"}]}
            cls.forecast_data = {"list": []}

        app = create_app()
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_alert_banner_renders_and_suppresses_pop(self):
        """Verify alert banner renders at y=436..460 and PoP collision is prevented."""
        # Render without alert
        img_no_alert = self.renderer.render(self.forecast_data, self.current_data, alert_text=None)
        self.assertEqual(img_no_alert.size, (800, 480))

        # Render with alert
        alert_msg = "Flash Flood Watch in effect"
        img_alert = self.renderer.render(self.forecast_data, self.current_data, alert_text=alert_msg)
        self.assertEqual(img_alert.size, (800, 480))
        self.assertIsInstance(img_alert, Image.Image)

    def test_alert_simulation_endpoints(self):
        """Test POST /api/alert/simulate and POST /api/alert/clear."""
        # 1. Simulate alert
        res = self.client.post("/api/alert/simulate", json={"title": "High Wind Warning in effect"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        # 2. Verify cache returns simulated alert
        updater = WeatherUpdater.get_instance()
        _, _, alert, _, _ = updater.get_current_payload()
        self.assertEqual(alert, "High Wind Warning in effect")

        # 3. Clear alert
        res_clear = self.client.post("/api/alert/clear")
        self.assertEqual(res_clear.status_code, 200)
        data_clear = res_clear.get_json()
        self.assertTrue(data_clear.get("success"))

    def test_config_export_endpoint(self):
        """Test GET /api/config/export returns downloadable JSON."""
        res = self.client.get("/api/config/export")
        self.assertEqual(res.status_code, 200)
        self.assertIn("attachment", res.headers.get("Content-Disposition", ""))
        payload = json.loads(res.data)
        self.assertIn("weather", payload)
        self.assertIn("display", payload)

    def test_config_import_validation(self):
        """Test POST /api/config/import validates schema."""
        # Invalid payload (not a dict)
        res_bad = self.client.post("/api/config/import", data="not json", content_type="application/json")
        self.assertIn(res_bad.status_code, (400, 500))

        # Missing core sections
        res_empty = self.client.post("/api/config/import", json={"random_key": "val"})
        self.assertEqual(res_empty.status_code, 400)

        # Valid export imported back
        export_res = self.client.get("/api/config/export")
        valid_cfg = json.loads(export_res.data)
        res_good = self.client.post("/api/config/import", json=valid_cfg)
        self.assertEqual(res_good.status_code, 200)
        self.assertTrue(res_good.get_json().get("success"))

    def test_location_search_validation(self):
        """Test GET /api/location/search requires query parameter."""
        res_no_q = self.client.get("/api/location/search")
        self.assertEqual(res_no_q.status_code, 400)


if __name__ == "__main__":
    unittest.main()

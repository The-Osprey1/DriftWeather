#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast E-Ink Weather Display - Main Entry Point
Modularized & modernized architecture with self-healing Wi-Fi watchdog,
conditional freshness indicator, and local Flask control panel.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Backward-compatible exports
from display.renderer import get_renderer, to_sharp_1bit, get_moon_phase, cubic_spline_coeffs, eval_spline
from weather.providers import WeatherProvider, c_to_f, mm_to_in
from weather.updater import get_weather_updater
from config.settings import get_settings

def draw_forecast(forecast_data, current_data, alert_text=None, aqi_text=None, kcno_obs=None, freshness_text=None):
    renderer = get_renderer()
    settings = get_settings().to_dict()
    return renderer.render(
        forecast_data, current_data,
        alert_text=alert_text,
        aqi_text=aqi_text,
        kcno_obs=kcno_obs,
        freshness_text=freshness_text,
        settings=settings
    )

def get_kcno_observation(station="KCNO"):
    provider = WeatherProvider(kcno_station=station)
    return provider.fetch_kcno_observation()

def load_weather_icon(icon_code, size=(46, 46), dark_mode=False):
    renderer = get_renderer()
    return renderer.load_weather_icon(icon_code, size=size, dark_mode=dark_mode)

def get_font(weight="bold", size=18):
    renderer = get_renderer()
    return renderer.get_font(weight, size)

if __name__ == "__main__":
    from main import main
    main()

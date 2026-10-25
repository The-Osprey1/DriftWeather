#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Weather Updater
Coordinates weather fetching, cache fallback, and notifies display listeners.
"""

import time
import logging
import threading
from typing import Optional, Callable, Dict, Any

from config.settings import get_settings
from .cache import WeatherCache
from .providers import WeatherProvider

logger = logging.getLogger("G4Cast.WeatherUpdater")

class WeatherUpdater:
    _instance = None
    _lock = threading.RLock()

    def __init__(self, cache: Optional[WeatherCache] = None):
        self.settings = get_settings()
        self.cache = cache if cache is not None else WeatherCache()
        self._listeners = []
        self.last_update_success = False
        self.last_sync_timestamp = 0.0

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def register_listener(self, listener: Callable[[dict, dict, Optional[str], Optional[str], Optional[dict]], None]):
        """Register a callback when weather data updates."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def refresh_weather(self, force_fetch: bool = False, is_online: bool = True) -> bool:
        """
        Fetch latest weather data from providers or fall back silently to cache.
        Returns True if fresh data was fetched, False if cache was used.
        """
        w_cfg = self.settings.get("weather", default={})
        city = w_cfg.get("city", "Eastvale, US")
        api_key = w_cfg.get("api_key", "")
        use_kcno = w_cfg.get("use_kcno", True)
        kcno_station = w_cfg.get("kcno_station", "KCNO")

        provider = WeatherProvider(api_key=api_key, city=city, kcno_station=kcno_station)

        current, forecast = None, None
        alert, aqi, kcno_obs = None, None, None
        fetched_live = False

        if is_online and api_key:
            logger.info("Fetching fresh live weather for %s...", city)
            current = provider.fetch_current()
            forecast = provider.fetch_forecast()

            if current and forecast:
                fetched_live = True
                coords = current.get("coord", {})
                lat = coords.get("lat", 33.963)
                lon = coords.get("lon", -117.564)
                tz_offset = current.get("timezone", -25200)

                # Secondary live integrations (silent failsafe)
                alert = provider.fetch_nws_alerts(lat, lon, tz_offset)
                aqi = provider.fetch_aqi(lat, lon)
                if aqi is None:
                    # Fallback retention: preserve existing cached AQI if live fetch returned None
                    _, _, _, cached_aqi, _ = self.cache.get_data()
                    aqi = cached_aqi
                if use_kcno:
                    kcno_obs = provider.fetch_kcno_observation()

                # Save to persistent cache
                self.cache.save(current, forecast, alert=alert, aqi=aqi, kcno=kcno_obs, source="live")
                self.last_update_success = True
                self.last_sync_timestamp = time.time()
                logger.info("Successfully fetched and cached live weather data.")

        # If live fetch failed or offline, fall back seamlessly to cache
        if not fetched_live:
            cached_curr, cached_fore, cached_alert, cached_aqi, cached_kcno = self.cache.get_data()
            if cached_curr and cached_fore:
                logger.warning("Using cached weather data (age: %.0f seconds)", self.cache.get_age_seconds())
                current, forecast = cached_curr, cached_fore
                alert, aqi, kcno_obs = cached_alert, cached_aqi, cached_kcno
                self.last_update_success = False
            else:
                logger.error("No weather data available (neither live nor cache)!")
                return False

        # Dispatch to all listeners (e.g. display renderer)
        self._notify_listeners(current, forecast, alert, aqi, kcno_obs)
        return fetched_live

    def _notify_listeners(self, current, forecast, alert, aqi, kcno):
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(current, forecast, alert, aqi, kcno)
            except Exception as e:
                logger.error("Error in weather update listener: %s", e)

    def get_current_payload(self):
        """Get latest available weather payload (current, forecast, alert, aqi, kcno)."""
        return self.cache.get_data()

    def simulate_alert(self, alert_text: str):
        """Inject simulated alert and notify listeners."""
        self.cache.set_simulated_alert(alert_text)
        curr, fore, alert, aqi, kcno = self.cache.get_data()
        self._notify_listeners(curr, fore, alert, aqi, kcno)

    def clear_simulated_alert(self):
        """Clear simulated alert and notify listeners."""
        self.cache.clear_simulated_alert()
        curr, fore, alert, aqi, kcno = self.cache.get_data()
        self._notify_listeners(curr, fore, alert, aqi, kcno)

def get_weather_updater():
    return WeatherUpdater.get_instance()

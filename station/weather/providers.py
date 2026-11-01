#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Weather Providers
Fetches live data from OpenWeatherMap, Chino Airport (KCNO) NOAA station, and NWS Severe Weather Alerts.
"""

import re
import json
import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger("G4Cast.Providers")

def c_to_f(c: float) -> int:
    return round(c * 9.0 / 5.0 + 32)

def mm_to_in(mm: float) -> float:
    return mm / 25.4

class WeatherProvider:
    def __init__(self, api_key: str = "", city: str = "Eastvale, US", kcno_station: str = "KCNO"):
        self.api_key = api_key
        self.city = city
        self.kcno_station = kcno_station

    def fetch_forecast(self) -> Optional[dict]:
        """Fetch 5-day / 3-hour forecast from OpenWeatherMap."""
        if not self.api_key or not self.city:
            logger.warning("API key or City not configured for forecast fetch")
            return None
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={self.city}&appid={self.api_key}"
        try:
            res = requests.get(url, timeout=12)
            if res.status_code == 200:
                return res.json()
            logger.error("Forecast API error HTTP %d: %s", res.status_code, res.text)
        except Exception as e:
            logger.error("Forecast request exception: %s", e)
        return None

    def fetch_current(self) -> Optional[dict]:
        """Fetch current weather from OpenWeatherMap."""
        if not self.api_key or not self.city:
            return None
        url = f"https://api.openweathermap.org/data/2.5/weather?q={self.city}&appid={self.api_key}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                return res.json()
            logger.error("Current weather API error HTTP %d: %s", res.status_code, res.text)
        except Exception as e:
            logger.error("Current weather request exception: %s", e)
        return None

    def fetch_kcno_observation(self) -> Optional[dict]:
        """
        Fetch hyper-local physical ground sensor observation from Chino Airport (KCNO) NOAA/NWS station.
        Provides ground-truth accuracy for Eastvale (4 miles away).
        """
        url = f"https://api.weather.gov/stations/{self.kcno_station}/observations/latest"
        headers = {"User-Agent": "G4CastWeatherStation/2.1 (contact@g4cast.local)"}
        try:
            try:
                res = requests.get(url, headers=headers, timeout=6)
            except Exception:
                res = requests.get(url, headers=headers, timeout=6, verify=False)

            if res.status_code == 200:
                props = res.json().get("properties", {})
                desc = props.get("textDescription")
                temp_c = props.get("temperature", {}).get("value")
                humidity = props.get("relativeHumidity", {}).get("value")
                wind_kmh = props.get("windSpeed", {}).get("value")
                icon_url = props.get("icon") or ""

                is_night = "/night/" in icon_url
                suffix = "n" if is_night else "d"

                m = re.search(r'/(?:day|night)/([a-z_]+)', icon_url)
                cond = m.group(1).lower() if m else ""

                if any(k in cond for k in ["ovc", "cloudy"]):
                    icon_code = f"04{suffix}"
                elif any(k in cond for k in ["bkn"]):
                    icon_code = f"04{suffix}"
                elif any(k in cond for k in ["sct"]):
                    icon_code = f"03{suffix}"
                elif any(k in cond for k in ["few"]):
                    icon_code = f"02{suffix}"
                elif any(k in cond for k in ["skc", "clear"]):
                    icon_code = f"01{suffix}"
                elif any(k in cond for k in ["fog", "mist", "haze"]):
                    icon_code = f"50{suffix}"
                elif any(k in cond for k in ["tsra", "thunder"]):
                    icon_code = f"11{suffix}"
                elif any(k in cond for k in ["rain", "shra"]):
                    icon_code = f"10{suffix}"
                elif any(k in cond for k in ["snow"]):
                    icon_code = f"13{suffix}"
                else:
                    icon_code = f"04{suffix}" if "cloud" in (desc or "").lower() else f"01{suffix}"

                clean_desc = desc if desc else "Clear"
                if "overcast" in clean_desc.lower():
                    clean_desc = "Overcast"
                elif "mostly cloudy" in clean_desc.lower():
                    clean_desc = "Mostly Cloudy"
                elif "partly cloudy" in clean_desc.lower():
                    clean_desc = "Partly Cloudy"

                return {
                    "description": clean_desc,
                    "temp_c": temp_c,
                    "humidity": round(humidity) if humidity is not None else None,
                    "wind_kmh": wind_kmh,
                    "icon": icon_code,
                    "station": self.kcno_station
                }
        except Exception as e:
            logger.warning("KCNO observation warning: %s", e)
        return None

    def fetch_nws_alerts(self, lat: float = 33.963, lon: float = -117.564, utc_offset_seconds: int = -25200) -> Optional[str]:
        """Fetch active severe weather warnings/advisories from api.weather.gov."""
        url = f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"
        headers = {
            "User-Agent": "G4CastWeatherStation/2.1 (contact@g4cast.local)",
            "Accept": "application/geo+json"
        }
        try:
            try:
                res = requests.get(url, headers=headers, timeout=6)
            except Exception:
                res = requests.get(url, headers=headers, timeout=6, verify=False)

            if res.status_code == 200:
                features = res.json().get("features", [])
                if not features:
                    return None

                # Find highest severity / priority active alert
                advisory = features[0].get("properties", {})
                event_name = advisory.get("event", "Weather Alert").upper()
                ends_raw = advisory.get("ends") or advisory.get("expires")

                end_str = ""
                if ends_raw:
                    try:
                        clean_ts = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', ends_raw)
                        dt = datetime.strptime(clean_ts, "%Y-%m-%dT%H:%M:%S%z") + timedelta(seconds=utc_offset_seconds)
                        end_str = dt.strftime("UNTIL %I %p %a").lstrip("0")
                    except Exception:
                        pass

                banner = f"! {event_name} - {end_str}" if end_str else f"! {event_name}"
                return banner
        except Exception as e:
            logger.warning("NWS alert fetch warning: %s", e)
        return None

    def fetch_aqi(self, lat: float = 33.963, lon: float = -117.564) -> Optional[str]:
        """Fetch EPA Air Quality Index from OpenWeatherMap."""
        if not self.api_key:
            return None
        url = "https://api.openweathermap.org/data/2.5/air_pollution"
        params = {"lat": lat, "lon": lon, "appid": self.api_key}
        try:
            res = requests.get(url, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json()
                items = data.get("list", [])
                if not items:
                    return None
                item = items[0]
                aqi_idx = item.get("main", {}).get("aqi", 1)
                aqi_map = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
                label = aqi_map.get(aqi_idx, "Good")
                return f"AQI: {label}"
        except Exception as e:
            logger.warning("AQI fetch warning: %s", e)
        return None

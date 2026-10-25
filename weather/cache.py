#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Weather Cache & Freshness Engine
Tracks live observation timestamps and formats subtle user-facing freshness indicators.
"""

import os
import json
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("G4Cast.WeatherCache")

class WeatherCache:
    _lock = threading.RLock()

    def __init__(self, cache_path: Optional[Path] = None):
        if cache_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            self.cache_path = base_dir / "weather_cache.json"
        else:
            self.cache_path = Path(cache_path)

        self.last_fetch_time: float = 0.0
        self.last_fetch_source: str = "cache"
        self._simulated_alert: Optional[str] = None
        self._cached_data: Dict[str, Any] = {}
        self.load()

    def load(self) -> bool:
        """Load weather cache from disk."""
        with self._lock:
            if not self.cache_path.exists():
                return False
            for attempt in range(3):
                try:
                    with open(self.cache_path, "r", encoding="utf-8") as f:
                        self._cached_data = json.load(f)
                    self.last_fetch_time = self._cached_data.get("timestamp", 0.0)
                    self.last_fetch_source = self._cached_data.get("source", "cache")
                    return True
                except (json.JSONDecodeError, UnicodeDecodeError) as err:
                    logger.error("Failed to parse weather cache %s: %s", self.cache_path, err)
                    return False
                except Exception as e:
                    if attempt < 2:
                        time.sleep(0.01)
                    else:
                        logger.error("Failed to load weather cache %s: %s", self.cache_path, e)
                        return False
            return False

    def save(self, current: dict, forecast: dict, alert: Optional[str] = None,
             aqi: Optional[str] = None, kcno: Optional[dict] = None, source: str = "live") -> bool:
        """Save fresh weather payload to disk."""
        with self._lock:
            # Fallback retention: preserve existing cached AQI if incoming aqi is None
            if aqi is None:
                if (not self._cached_data or self._cached_data.get("aqi") is None) and self.cache_path.exists():
                    self.load()
                if self._cached_data:
                    aqi = self._cached_data.get("aqi")

            self.last_fetch_time = time.time()
            self.last_fetch_source = source
            self._cached_data = {
                "current": current,
                "forecast": forecast,
                "alert": alert,
                "aqi": aqi,
                "kcno": kcno,
                "timestamp": self.last_fetch_time,
                "source": source
            }

            # Unique temporary filename to eliminate concurrent collisions on Windows
            temp_file = self.cache_path.with_name(
                f"{self.cache_path.stem}_{threading.get_ident()}_{time.time_ns()}.tmp"
            )
            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self._cached_data, f, indent=2)

                # Atomic replace with retry for Windows file locking contention
                for attempt in range(5):
                    try:
                        os.replace(temp_file, self.cache_path)
                        break
                    except OSError:
                        if attempt < 4:
                            time.sleep(0.01 * (attempt + 1))
                        else:
                            raise

                logger.info("Saved fresh weather cache to %s", self.cache_path)
                return True
            except Exception as e:
                logger.error("Failed to save weather cache: %s", e)
                return False
            finally:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except OSError:
                        pass

    def get_data(self) -> Tuple[Optional[dict], Optional[dict], Optional[str], Optional[str], Optional[dict]]:
        """Returns (current, forecast, alert, aqi, kcno)."""
        with self._lock:
            alert = self._simulated_alert if self._simulated_alert is not None else self._cached_data.get("alert")
            return (
                self._cached_data.get("current"),
                self._cached_data.get("forecast"),
                alert,
                self._cached_data.get("aqi"),
                self._cached_data.get("kcno")
            )

    def set_simulated_alert(self, alert_text: str):
        """Set temporary in-memory simulated alert without modifying persistent cache."""
        with self._lock:
            self._simulated_alert = alert_text

    def clear_simulated_alert(self):
        """Clear temporary simulated alert."""
        with self._lock:
            self._simulated_alert = None

    def get_age_seconds(self) -> float:
        """Get age of cached weather data in seconds."""
        with self._lock:
            if self.last_fetch_time <= 0:
                return 999999.0
            return max(0.0, time.time() - self.last_fetch_time)

    def get_freshness_status(self, is_online: bool = True) -> Optional[str]:
        """
        Returns the formatted status label for the e-paper display:
        - Normal (< 45 min): None (clean, uncluttered layout)
        - Slightly stale (45–90 min): 'Updated 48m ago'
        - Offline / Stale (> 90 min or offline): 'OFFLINE · Updated 2h ago'
        """
        age = self.get_age_seconds()
        age_minutes = int(age // 60)
        age_hours = int(age // 3600)

        # 1. Normal state: completely clean display
        if is_online and age < (45 * 60):
            return None

        # Format time ago
        if age_hours >= 1:
            time_ago = f"{age_hours}h ago"
        else:
            time_ago = f"{max(1, age_minutes)}m ago"

        # 2. Offline / Long stale state
        if (not is_online) or (age >= 90 * 60):
            return f"OFFLINE \u00b7 Updated {time_ago}"

        # 3. Slightly stale state
        return f"Updated {time_ago}"

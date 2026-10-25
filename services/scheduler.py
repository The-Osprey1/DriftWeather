#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Master Scheduler & Display Controller
Coordinates periodic weather updates, 1-minute clock updates, customizable quiet hours,
and daily calibration deep-purges.
"""

import time
import math
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Any

from config.settings import get_settings, normalize_dark_mode
from display.renderer import get_renderer
from display.epaper import get_display
from weather.updater import get_weather_updater
from .wifi_watchdog import get_wifi_watchdog

logger = logging.getLogger("G4Cast.Scheduler")

def calculate_astronomical_solar(
    lat: float,
    lon: float,
    dt: Optional[datetime] = None,
    tz_offset_seconds: int = -25200
) -> Tuple[Optional[float], Optional[float]]:
    """
    Computes astronomical sunrise and sunset in local minutes from midnight [0..1440)
    using standard NOAA solar position equations.
    Returns (sunrise_local_minutes, sunset_local_minutes).
    For polar night returns (None, None).
    For polar day / midnight sun returns (-1.0, -1.0).
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    day_of_year = dt.timetuple().tm_yday
    gamma = 2.0 * math.pi / 365.25 * (day_of_year - 1 + (dt.hour - 12) / 24.0)

    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )

    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )

    lat_rad = math.radians(lat)
    zenith_rad = math.radians(90.833)  # Official NOAA refraction zenith

    num = math.cos(zenith_rad) - math.sin(lat_rad) * math.sin(decl)
    denom = math.cos(lat_rad) * math.cos(decl)
    if abs(denom) < 1e-7:
        if num > 0:
            return (None, None)  # Polar night / sun never rises
        else:
            return (-1.0, -1.0)  # Polar day / midnight sun / sun never sets
    else:
        cos_ha = num / denom

    if cos_ha >= 1.0:
        return (None, None)  # Polar night
    elif cos_ha <= -1.0:
        return (-1.0, -1.0)  # Polar day / midnight sun

    ha = math.degrees(math.acos(cos_ha))
    sunrise_utc = 720.0 - 4.0 * (lon + ha) - eqtime
    sunset_utc = 720.0 - 4.0 * (lon - ha) - eqtime

    tz_offset_min = tz_offset_seconds / 60.0
    sunrise_local = (sunrise_utc + tz_offset_min) % 1440.0
    sunset_local = (sunset_utc + tz_offset_min) % 1440.0

    return (sunrise_local, sunset_local)

def evaluate_dark_mode(
    mode: Any = "auto",
    weather_data: Optional[dict] = None,
    lat: float = 33.963,
    lon: float = -117.564,
    current_time: Optional[datetime] = None,
    now_dt: Optional[datetime] = None
) -> bool:
    """
    Evaluates whether Dark Mode should be active given the mode setting,
    weather observation cache, and geographical coordinates.
    - If mode is 'off', returns False.
    - If mode is 'on', returns True.
    - If mode is 'auto':
      - Extracts sunrise and sunset from weather_data.
      - Normalizes to minutes-from-midnight (0..1439) to protect against stale cache lockup.
      - Falls back to pure-Python NOAA astronomical equations if weather_data is None or invalid.
    """
    mode_norm = normalize_dark_mode(mode)
    if mode_norm == "off":
        return False
    if mode_norm == "on":
        return True

    # Mode is "auto"
    if current_time is None and now_dt is not None:
        current_time = now_dt
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    elif current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    weather = weather_data if isinstance(weather_data, dict) else {}
    tz_raw = weather.get("timezone", -25200)
    try:
        tz_offset = int(tz_raw)
        if not (-86400 <= tz_offset <= 86400):
            tz_offset = -25200
    except (ValueError, TypeError, OverflowError):
        tz_offset = -25200

    # Extract coordinates from weather if available
    coords = weather.get("coord", {})
    if isinstance(coords, dict):
        if "lat" in coords and coords["lat"] is not None:
            try:
                lat = float(coords["lat"])
            except (ValueError, TypeError, OverflowError):
                pass
        if "lon" in coords and coords["lon"] is not None:
            try:
                lon = float(coords["lon"])
            except (ValueError, TypeError, OverflowError):
                pass

    # Compute current local minute-of-day [0..1440)
    utc_dt = current_time.astimezone(timezone.utc)
    try:
        local_dt = utc_dt + timedelta(seconds=tz_offset)
    except (ValueError, TypeError, OverflowError):
        tz_offset = -25200
        local_dt = utc_dt + timedelta(seconds=-25200)
    local_tod = local_dt.hour * 60 + local_dt.minute

    sr_tod = None
    ss_tod = None

    sys_data = weather.get("sys", {})
    if isinstance(sys_data, dict):
        sr_ts = sys_data.get("sunrise")
        ss_ts = sys_data.get("sunset")
        if sr_ts and ss_ts:
            try:
                sr_dt = datetime.fromtimestamp(sr_ts, timezone.utc) + timedelta(seconds=tz_offset)
                ss_dt = datetime.fromtimestamp(ss_ts, timezone.utc) + timedelta(seconds=tz_offset)
                sr_tod = sr_dt.hour * 60 + sr_dt.minute
                ss_tod = ss_dt.hour * 60 + ss_dt.minute
            except Exception as e:
                logger.warning("Error parsing cached solar timestamps: %s", e)
                sr_tod = None
                ss_tod = None

    # Fallback to offline NOAA astronomical calculation if cache is missing, corrupted, or equal
    if sr_tod is None or ss_tod is None or sr_tod == ss_tod:
        try:
            astro_sr, astro_ss = calculate_astronomical_solar(lat, lon, current_time, tz_offset)
            if astro_sr is None:  # Polar night
                return True
            if astro_sr == -1.0:  # Polar day / midnight sun
                return False
            sr_tod = int(round(astro_sr))
            ss_tod = int(round(astro_ss))
        except Exception as e:
            logger.error("Astronomical solar calculation fallback error: %s", e)
            # Default fallback: daytime between 06:30 and 19:30
            return not (390 <= local_tod < 1170)

    if sr_tod <= ss_tod:
        is_day = (sr_tod <= local_tod < ss_tod)
    else:
        is_day = (local_tod >= sr_tod or local_tod < ss_tod)

    return not is_day

class DisplayScheduler:
    _instance = None
    _lock = threading.RLock()

    def __init__(self):
        self.settings = get_settings()
        self.renderer = get_renderer()
        self.display = get_display()
        self.updater = get_weather_updater()
        self.watchdog = get_wifi_watchdog()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.last_weather_update = 0.0
        self.current_is_dark: Optional[bool] = None

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True

            # Register watchdog recovery callback: instant refresh when connectivity returns!
            self.watchdog.register_recovery_callback(self.on_network_recovered)

            self._thread = threading.Thread(target=self._main_loop, name="DisplaySchedulerThread", daemon=True)
            self._thread.start()
            logger.info("Display scheduler started successfully.")

    def stop(self):
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def is_in_quiet_hours(self) -> bool:
        """Check if current time falls within configured quiet hours window."""
        q_cfg = self.settings.get("quiet_hours", default={})
        if not q_cfg.get("enabled", True):
            return False

        start_str = q_cfg.get("start_time", "23:00")
        end_str = q_cfg.get("end_time", "06:00")

        curr, _, _, _, _ = self.updater.get_current_payload()
        if curr and "timezone" in curr:
            utc_now = datetime.now(timezone.utc)
            now = (utc_now + timedelta(seconds=curr["timezone"])).time()
        else:
            now = datetime.now().time()

        try:
            start_t = datetime.strptime(start_str, "%H:%M").time()
            end_t = datetime.strptime(end_str, "%H:%M").time()
        except Exception:
            start_t = datetime.strptime("23:00", "%H:%M").time()
            end_t = datetime.strptime("06:00", "%H:%M").time()

        if start_t <= end_t:
            # Daytime quiet window, e.g. 13:00 to 15:00
            return start_t <= now < end_t
        else:
            # Overnight window across midnight, e.g. 23:00 to 06:00
            return now >= start_t or now < end_t

    def evaluate_dark_mode(self, weather_data: Optional[dict] = None, now_dt: Optional[datetime] = None) -> bool:
        """Evaluate effective dark mode based on settings, weather cache, and coordinates."""
        mode = self.settings.get("display", "dark_mode", default="off")
        coords = weather_data.get("coord", {}) if isinstance(weather_data, dict) else {}
        lat = float(coords.get("lat", 33.963))
        lon = float(coords.get("lon", -117.564))
        return evaluate_dark_mode(mode, weather_data=weather_data, lat=lat, lon=lon, current_time=now_dt)

    def update_display_now(self, force_full: bool = False, is_quiet_wake: bool = False):
        """Render fresh image from weather data and update physical e-paper display."""
        curr, fore, alert, aqi, kcno = self.updater.get_current_payload()
        if not curr or not fore:
            logger.warning("No weather payload available to render.")
            return

        is_online = self.watchdog.is_connected
        freshness_str = self.updater.cache.get_freshness_status(is_online=is_online)

        settings_dict = self.settings.to_dict()
        rotation = settings_dict.get("display", {}).get("rotation", 180)

        is_dark = self.evaluate_dark_mode(weather_data=curr)
        self.current_is_dark = is_dark
        settings_dict.setdefault("display", {})["dark_mode"] = is_dark

        img = self.renderer.render(
            fore, curr,
            alert_text=alert,
            aqi_text=aqi,
            kcno_obs=kcno,
            freshness_text=freshness_str,
            settings=settings_dict,
            dark_mode=is_dark
        )

        self.display.display_image(img, force_full=force_full, rotation=rotation)
        self.last_weather_update = time.time()

    def on_network_recovered(self):
        """Callback triggered immediately by Wi-Fi watchdog upon connection restoration."""
        logger.info("Scheduler: Network restored notification received. Triggering instant refresh!")
        self.updater.refresh_weather(force_fetch=True, is_online=True)
        # Check if in quiet hours
        if not self.is_in_quiet_hours():
            self.update_display_now(force_full=False)
        else:
            logger.info("Currently in quiet hours: updated weather data in memory, skipping screen wake.")

    def update_clock(self, animate: bool = True):
        """Update digital clock via sub-second partial e-paper refresh."""
        try:
            if self.is_in_quiet_hours():
                logger.debug("Quiet hours active: skipping minute clock partial refresh.")
                return

            curr, _, _, _, _ = self.updater.get_current_payload()
            tz_offset = curr.get("timezone", -25200) if curr else -25200
            utc_now = datetime.now(timezone.utc)
            local_dt = utc_now + timedelta(seconds=tz_offset)

            use_24h = self.settings.get("display", "use_24h_format", default=False)
            rotation = self.settings.get("display", "rotation", default=180)

            is_dark = self.evaluate_dark_mode(weather_data=curr, now_dt=utc_now)

            # Detect solar sunrise/sunset transition
            if self.current_is_dark is not None and is_dark != self.current_is_dark:
                logger.info(
                    "Solar transition detected (%s -> %s). Triggering full display refresh.",
                    "dark" if self.current_is_dark else "light",
                    "dark" if is_dark else "light"
                )
                self.current_is_dark = is_dark
                self.update_display_now(force_full=True)
                return

            self.current_is_dark = is_dark

            if self.renderer.current_image:
                self.display.update_clock_partial(
                    self.renderer.current_image,
                    local_dt,
                    self.renderer.get_font,
                    use_24h=use_24h,
                    dark_mode=is_dark,
                    rotation=rotation,
                    animate=animate
                )
        except Exception as e:
            logger.error("Error in update_clock: %s", e, exc_info=True)

    def _main_loop(self):
        # 1. Initial boot update
        try:
            self.updater.refresh_weather(force_fetch=True, is_online=self.watchdog.is_connected)
            self.update_display_now(force_full=True)
        except Exception as e:
            logger.error("Error during initial display update: %s", e, exc_info=True)

        last_clock_minute = datetime.now().minute

        while self._running:
            try:
                now = datetime.now()
                minute = now.minute
                second = now.second

                # 1. Check periodic weather refresh interval (default: every 30 minutes at :00 and :30)
                update_interval = self.settings.get("weather", "update_interval_minutes", default=30)
                if minute % update_interval == 0 and second < 5:
                    deep_purge_hour = self.settings.get("display", "deep_purge_hour", default=3)
                    is_deep_purge = (now.hour == deep_purge_hour and minute == 0)

                    # Weather can ALWAYS download in background during quiet hours
                    self.updater.refresh_weather(force_fetch=True, is_online=self.watchdog.is_connected)

                    in_quiet = self.is_in_quiet_hours()
                    allow_severe = self.settings.get("quiet_hours", "allow_severe_alerts", default=True)
                    _, _, alert, _, _ = self.updater.get_current_payload()

                    if not in_quiet or (in_quiet and allow_severe and alert):
                        self.update_display_now(force_full=is_deep_purge)
                    else:
                        logger.debug("Quiet hours active: weather cached in memory, display refresh skipped.")

                    last_clock_minute = minute
                    time.sleep(5)  # Avoid re-triggering in same 5s window
                    continue

                # 2. Minute clock update (every minute when minute increments)
                if minute != last_clock_minute:
                    self.update_clock(animate=True)
                    last_clock_minute = minute

                time.sleep(1)
            except Exception as e:
                logger.error("Error in scheduler main loop: %s", e, exc_info=True)
                time.sleep(2)

def get_scheduler():
    return DisplayScheduler.get_instance()

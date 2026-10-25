#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Shared Settings Manager
Handles loading, saving, and transparent OverlayFS persistence for all G4Cast components.
"""

import os
import json
import logging
import subprocess
import threading
from pathlib import Path
from copy import deepcopy

logger = logging.getLogger("G4Cast.Settings")

def normalize_dark_mode(val) -> str:
    """Normalize dark mode configuration value to 'off', 'on', or 'auto'."""
    if isinstance(val, bool):
        return "on" if val else "off"
    if isinstance(val, (int, float)):
        return "on" if val == 1 else "off"
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("on", "true", "1", "yes", "dark"):
            return "on"
        elif v in ("auto", "solar", "automatic"):
            return "auto"
        elif v in ("off", "false", "0", "no", "light"):
            return "off"
    return "off"

def normalize_layout_style(val) -> str:
    """Normalize layout style configuration value to 'classic', 'widgets', 'dualtone', or 'minimalist'."""
    if val is not None:
        v = str(val).strip().lower()
        if v in ("widgets", "widget", "tiles", "option1", "1"):
            return "widgets"
        elif v in ("dualtone", "dual-tone", "dual_tone", "inverted", "option2", "2"):
            return "dualtone"
        elif v in ("minimalist", "minimal", "editorial", "option3", "3"):
            return "minimalist"
        elif v in ("classic", "default", "standard", "option4", "4"):
            return "classic"
    return "classic"

def normalize_hero_size(val) -> str:
    """Normalize hero temperature sizing to 'compact', 'standard', or 'large'."""
    if val is not None:
        v = str(val).strip().lower()
        if v in ("large", "huge", "big", "glanceable", "104", "105"):
            return "large"
        elif v in ("compact", "small", "dense", "68", "64"):
            return "compact"
        elif v in ("standard", "normal", "medium", "default", "84"):
            return "standard"
    return "standard"

class Settings:
    _instance = None
    _lock = threading.RLock()

    def __init__(self, config_dir=None):
        if config_dir is None:
            self.base_dir = Path(__file__).resolve().parent.parent
            self.config_dir = self.base_dir / "config"
        else:
            self.config_dir = Path(config_dir)
            self.base_dir = self.config_dir.parent

        self.settings_file = self.config_dir / "settings.json"
        self.default_file = self.config_dir / "default_settings.json"
        self.is_linux = (os.name != "nt")
        self.legacy_txt = Path("/boot/firmware/G4Cast/G4CastData.txt") if self.is_linux else None
        self.overlay_root = Path("/media/root-ro") if self.is_linux else None
        self._data = {}
        self.load()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load_default(self):
        if self.default_file.exists():
            try:
                with open(self.default_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load default settings: {e}")
        return {
            "weather": {
                "city": "Eastvale, US",
                "display_text": "Eastvale",
                "api_key": "",
                "use_metric": False,
                "use_kcno": True,
                "kcno_station": "KCNO",
                "use_avg_temp": False,
                "update_interval_minutes": 30
            },
            "display": {
                "use_24h_format": False,
                "dark_mode": "off",
                "layout_style": "classic",
                "hero_size": "standard",
                "rotation": 180,
                "full_refresh_cycles": 24,
                "deep_purge_hour": 3
            },
            "quiet_hours": {
                "enabled": True,
                "start_time": "23:00",
                "end_time": "06:00",
                "allow_severe_alerts": True
            },
            "network": {
                "watchdog_enabled": True,
                "ping_host": "1.1.1.1",
                "check_interval_seconds": 30,
                "max_reconnect_attempts": 3
            },
            "web": {
                "port": 8080,
                "host": "0.0.0.0"
            },
            "version": "2.1.0"
        }

    def _import_legacy_txt(self, data):
        """Import legacy G4CastData.txt if settings.json does not exist yet."""
        if not self.legacy_txt or not self.legacy_txt.exists():
            return data
        try:
            with open(self.legacy_txt, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip().upper(), v.strip()
                    if k == "CITY" and v:
                        data["weather"]["city"] = v
                    elif k == "API_KEY" and v:
                        data["weather"]["api_key"] = v
                    elif k == "DISPLAY_TEXT" and v:
                        data["weather"]["display_text"] = v
                    elif k == "USE_METRIC":
                        data["weather"]["use_metric"] = v.lower() in ("true", "1", "yes")
                    elif k == "USE_24HFORMAT":
                        data["display"]["use_24h_format"] = v.lower() in ("true", "1", "yes")
                    elif k == "DARK_MODE":
                        data["display"]["dark_mode"] = normalize_dark_mode(v)
            logger.info("Migrated existing legacy configuration from G4CastData.txt")
        except Exception as e:
            logger.warning(f"Legacy import error: {e}")
        return data

    def load(self):
        with self._lock:
            default_data = self._load_default()
            if self.settings_file.exists():
                try:
                    with open(self.settings_file, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    self._data = self._deep_merge(default_data, loaded)
                    if "display" in self._data:
                        if "dark_mode" in self._data["display"]:
                            self._data["display"]["dark_mode"] = normalize_dark_mode(self._data["display"]["dark_mode"])
                        if "layout_style" in self._data["display"]:
                            self._data["display"]["layout_style"] = normalize_layout_style(self._data["display"]["layout_style"])
                        if "hero_size" in self._data["display"]:
                            self._data["display"]["hero_size"] = normalize_hero_size(self._data["display"]["hero_size"])
                    return deepcopy(self._data)
                except Exception as e:
                    logger.error(f"Error loading {self.settings_file}: {e}; falling back to defaults")
            # If settings.json doesn't exist, try importing legacy then save
            merged = self._import_legacy_txt(default_data)
            self._data = merged
            if "display" in self._data and "dark_mode" in self._data["display"]:
                self._data["display"]["dark_mode"] = normalize_dark_mode(self._data["display"]["dark_mode"])
            self.save(persist=False)
            return deepcopy(self._data)

    def _deep_merge(self, base, override):
        res = deepcopy(base)
        for k, v in override.items():
            if k in res and isinstance(res[k], dict) and isinstance(v, dict):
                res[k] = self._deep_merge(res[k], v)
            else:
                res[k] = v
        return res

    def get(self, *keys, default=None):
        """Retrieve nested setting via key path, e.g. get('weather', 'city')"""
        with self._lock:
            curr = self._data
            for k in keys:
                if isinstance(curr, dict) and k in curr:
                    curr = curr[k]
                else:
                    return default
            return deepcopy(curr)

    def set(self, *keys_and_value):
        """Set nested setting e.g. set('weather', 'city', 'Eastvale, US')"""
        if len(keys_and_value) < 2:
            raise ValueError("Need at least one key and a value")
        keys = keys_and_value[:-1]
        val = keys_and_value[-1]
        if (len(keys) == 2 and keys[0] == "display" and keys[1] == "dark_mode") or (len(keys) == 1 and keys[0] == "dark_mode"):
            val = normalize_dark_mode(val)
        elif (len(keys) == 2 and keys[0] == "display" and keys[1] == "layout_style") or (len(keys) == 1 and keys[0] == "layout_style"):
            val = normalize_layout_style(val)
        elif (len(keys) == 2 and keys[0] == "display" and keys[1] == "hero_size") or (len(keys) == 1 and keys[0] == "hero_size"):
            val = normalize_hero_size(val)
        with self._lock:
            curr = self._data
            for k in keys[:-1]:
                if k not in curr or not isinstance(curr[k], dict):
                    curr[k] = {}
                curr = curr[k]
            curr[keys[-1]] = val

    def update(self, new_dict, persist=True):
        """Bulk update settings from dictionary"""
        with self._lock:
            self._data = self._deep_merge(self._data, new_dict)
            if "display" in self._data:
                if "dark_mode" in self._data["display"]:
                    self._data["display"]["dark_mode"] = normalize_dark_mode(self._data["display"]["dark_mode"])
                if "layout_style" in self._data["display"]:
                    self._data["display"]["layout_style"] = normalize_layout_style(self._data["display"]["layout_style"])
                if "hero_size" in self._data["display"]:
                    self._data["display"]["hero_size"] = normalize_hero_size(self._data["display"]["hero_size"])
        return self.save(persist=persist)

    def to_dict(self):
        with self._lock:
            return deepcopy(self._data)

    def save(self, persist=True, sync=False):
        """Save settings to config/settings.json and sync to OverlayFS if on Pi."""
        with self._lock:
            data_to_save = deepcopy(self._data)

        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            temp_file = self.settings_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=2)
            os.replace(temp_file, self.settings_file)
            logger.info("Saved settings to %s", self.settings_file)
        except Exception as e:
            logger.error(f"Failed to write settings file: {e}")
            return False

        if persist:
            if sync:
                self._persist_to_overlayfs()
            else:
                threading.Thread(target=self._persist_to_overlayfs, daemon=True).start()

        return True

    def _persist_to_overlayfs(self):
        """Safely persist settings.json to underlying physical filesystem."""
        if not self.overlay_root or not self.overlay_root.exists():
            return True

        target_dir = self.overlay_root / str(self.config_dir).lstrip("/")
        target_file = target_dir / "settings.json"

        cmd = f"mount -o remount,rw /media/root-ro && mkdir -p '{target_dir}' && cp '{self.settings_file}' '{target_file}' && mount -o remount,ro /media/root-ro"
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                logger.info("Successfully persisted settings to %s", target_file)
                return True
            else:
                logger.warning("OverlayFS persist warning: %s", res.stderr)
        except Exception as e:
            logger.warning(f"OverlayFS persist error: {e}")
        return False

def get_settings():
    return Settings.get_instance()

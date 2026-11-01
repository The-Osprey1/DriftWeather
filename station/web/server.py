#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Local Web Control Panel
Lightweight Flask web application providing live display preview mirror,
one-click display management, configuration editing, and hardware diagnostics.
"""

import io
import json
import time
import logging
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response

from config.settings import get_settings, normalize_dark_mode, normalize_layout_style, normalize_hero_size
from display.renderer import get_renderer
from display.epaper import get_display
from weather.updater import get_weather_updater
from services.wifi_watchdog import get_wifi_watchdog
from services.health import get_health
from services.scheduler import evaluate_dark_mode, calculate_astronomical_solar

logger = logging.getLogger("G4Cast.Web")

def create_app() -> Flask:
    template_dir = Path(__file__).resolve().parent / "templates"
    static_dir = Path(__file__).resolve().parent / "static"

    app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))
    app.config["JSON_SORT_KEYS"] = False

    settings = get_settings()
    renderer = get_renderer()
    display = get_display()
    updater = get_weather_updater()
    watchdog = get_wifi_watchdog()
    health = get_health()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/preview.png")
    def preview_png():
        """Serve live 800x480 PNG preview mirror."""
        png_bytes = renderer.get_current_png_bytes()
        if png_bytes:
            return Response(png_bytes, mimetype="image/png")

        # Fallback: render latest payload if no image in memory yet
        curr, fore, alert, aqi, kcno = updater.get_current_payload()
        if curr and fore:
            freshness = updater.cache.get_freshness_status(is_online=watchdog.is_connected)
            img = renderer.render(fore, curr, alert_text=alert, aqi_text=aqi, kcno_obs=kcno,
                                  freshness_text=freshness, settings=settings.to_dict())
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return Response(buf.getvalue(), mimetype="image/png")

        # Return a 1x1 dummy transparent png
        dummy = io.BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
        return Response(dummy.getvalue(), mimetype="image/png")

    @app.route("/api/status")
    def status():
        """Live header summary status."""
        age = updater.cache.get_age_seconds()
        age_min = max(0, int(age // 60))
        if age_min < 1:
            age_str = "just now"
        elif age_min < 60:
            age_str = f"{age_min} min ago"
        else:
            age_str = f"{age_min // 60}h ago"

        city = settings.get("weather", "display_text", default=settings.get("weather", "city", default="Eastvale"))

        return jsonify({
            "is_online": watchdog.is_connected,
            "city": city,
            "updated_str": age_str,
            "updated_seconds": round(age),
            "refresh_count": display.refresh_count
        })

    @app.route("/api/refresh", methods=["POST"])
    def refresh_display():
        """Trigger an immediate weather fetch and display refresh."""
        try:
            logger.info("Web API: Manual display refresh requested")
            # Force live fetch
            updater.refresh_weather(force_fetch=True, is_online=watchdog.is_connected)

            from services.scheduler import get_scheduler
            scheduler = get_scheduler()
            scheduler.update_display_now(force_full=False)

            return jsonify({"success": True, "message": "Display refreshed successfully."})
        except Exception as e:
            logger.error(f"Manual refresh error: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/clean", methods=["POST"])
    def clean_display():
        """Trigger a deep e-paper cleaning cycle to remove ghosting."""
        try:
            logger.info("Web API: Manual clean display requested")
            display.clean_display()

            # Re-draw the weather layout
            from services.scheduler import get_scheduler
            scheduler = get_scheduler()
            scheduler.update_display_now(force_full=True)

            return jsonify({"success": True, "message": "Screen cleaned and refreshed."})
        except Exception as e:
            logger.error(f"Clean display error: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    def _enrich_settings(settings_data: dict) -> dict:
        res = dict(settings_data)
        disp = dict(res.get("display", {}))
        raw_mode = disp.get("dark_mode", "off")
        mode = normalize_dark_mode(raw_mode)
        disp["dark_mode"] = mode
        disp["layout_style"] = normalize_layout_style(disp.get("layout_style", "classic"))
        disp["hero_size"] = normalize_hero_size(disp.get("hero_size", "standard"))

        curr = None
        if updater is not None:
            try:
                curr, _, _, _, _ = updater.get_current_payload()
            except Exception:
                pass

        lat = 33.963
        lon = -117.564
        if curr and isinstance(curr, dict) and "coord" in curr:
            lat = float(curr["coord"].get("lat", lat))
            lon = float(curr["coord"].get("lon", lon))

        is_dark = evaluate_dark_mode(mode, weather_data=curr, lat=lat, lon=lon)
        disp["is_dark"] = is_dark

        solar_summary = ""
        if curr and isinstance(curr, dict) and "sys" in curr:
            sr_ts = curr["sys"].get("sunrise", 0)
            ss_ts = curr["sys"].get("sunset", 0)
            tz_offset = curr.get("timezone", -25200)
            if sr_ts and ss_ts:
                sr_dt = datetime.fromtimestamp(sr_ts, timezone.utc) + timedelta(seconds=tz_offset)
                ss_dt = datetime.fromtimestamp(ss_ts, timezone.utc) + timedelta(seconds=tz_offset)
                solar_summary = f"Sunrise {sr_dt.strftime('%I:%M %p')}, Sunset {ss_dt.strftime('%I:%M %p')}"
        if not solar_summary:
            sr_s, ss_s = calculate_astronomical_solar(lat, lon)
            if sr_s is not None and ss_s is not None:
                sr_h, sr_m = int(sr_s // 60), int(sr_s % 60)
                ss_h, ss_m = int(ss_s // 60), int(ss_s % 60)
                solar_summary = f"Sunrise {sr_h:02d}:{sr_m:02d}, Sunset {ss_h:02d}:{ss_m:02d} (Solar)"

        disp["solar_summary"] = solar_summary
        res["display"] = disp
        return res

    @app.route("/api/settings", methods=["GET"])
    def get_settings_endpoint():
        return jsonify(_enrich_settings(settings.to_dict()))

    @app.route("/api/settings", methods=["POST"])
    def update_settings_endpoint():
        try:
            payload = request.get_json(force=True)
            if not isinstance(payload, dict):
                return jsonify({"success": False, "error": "Invalid payload format"}), 400

            if "display" in payload and isinstance(payload["display"], dict):
                if "dark_mode" in payload["display"]:
                    payload["display"]["dark_mode"] = normalize_dark_mode(payload["display"]["dark_mode"])
                if "layout_style" in payload["display"]:
                    payload["display"]["layout_style"] = normalize_layout_style(payload["display"]["layout_style"])
                if "hero_size" in payload["display"]:
                    payload["display"]["hero_size"] = normalize_hero_size(payload["display"]["hero_size"])

            success = settings.update(payload, persist=True)

            # Immediately update the display with the new settings
            try:
                from services.scheduler import get_scheduler
                scheduler = get_scheduler()
                scheduler.update_display_now(force_full=False)
            except Exception as ex:
                logger.debug(f"Display update trigger note: {ex}")

            return jsonify({
                "success": success,
                "message": "Settings updated and saved persistently.",
                "settings": _enrich_settings(settings.to_dict())
            })
        except Exception as e:
            logger.error(f"Settings update error: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/network/reconnect", methods=["POST"])
    def network_reconnect():
        try:
            watchdog.attempt_recovery()
            return jsonify({"success": True, "message": "Reconnection sequence initiated."})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/diagnostics")
    def diagnostics():
        data = health.get_full_diagnostics(weather_updater=updater, display=display)
        return jsonify(data)

    @app.route("/api/alert/simulate", methods=["POST"])
    def alert_simulate():
        try:
            payload = request.get_json(silent=True) or {}
            title = payload.get("title", "High Wind Warning in effect")
            updater.simulate_alert(title)
            from services.scheduler import get_scheduler
            scheduler = get_scheduler()
            scheduler.update_display_now(force_full=False)
            return jsonify({"success": True, "message": f"Simulated alert set: {title}"})
        except Exception as e:
            logger.error("Alert simulation error: %s", e)
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/alert/clear", methods=["POST"])
    def alert_clear():
        try:
            updater.clear_simulated_alert()
            from services.scheduler import get_scheduler
            scheduler = get_scheduler()
            scheduler.update_display_now(force_full=False)
            return jsonify({"success": True, "message": "Simulated alert cleared."})
        except Exception as e:
            logger.error("Alert clear error: %s", e)
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/config/export", methods=["GET"])
    def config_export():
        try:
            raw_data = settings.to_dict()
            content = json.dumps(raw_data, indent=2)
            return Response(
                content,
                mimetype="application/json",
                headers={"Content-Disposition": "attachment; filename=g4cast_settings.json"}
            )
        except Exception as e:
            logger.error("Config export error: %s", e)
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/config/import", methods=["POST"])
    def config_import():
        try:
            if "file" in request.files:
                uploaded_file = request.files["file"]
                content = uploaded_file.read().decode("utf-8")
                payload = json.loads(content)
            else:
                payload = request.get_json(silent=True)
                if payload is None:
                    raw_text = request.get_data(as_text=True)
                    try:
                        payload = json.loads(raw_text) if raw_text else None
                    except Exception:
                        payload = None

            if not isinstance(payload, dict):
                return jsonify({"success": False, "error": "Imported configuration must be a JSON object"}), 400

            core_sections = {"weather", "display", "quiet_hours", "network"}
            if not any(k in payload for k in core_sections):
                return jsonify({"success": False, "error": "Invalid schema: Missing expected configuration sections"}), 400

            if "display" in payload and isinstance(payload["display"], dict) and "dark_mode" in payload["display"]:
                payload["display"]["dark_mode"] = normalize_dark_mode(payload["display"]["dark_mode"])

            success = settings.update(payload, persist=True)
            from services.scheduler import get_scheduler
            scheduler = get_scheduler()
            scheduler.update_display_now(force_full=False)

            return jsonify({
                "success": success,
                "message": "Configuration successfully imported and saved persistently.",
                "settings": _enrich_settings(settings.to_dict())
            })
        except Exception as e:
            logger.error("Config import error: %s", e)
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/location/search", methods=["GET"])
    def location_search():
        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({"success": False, "results": [], "error": "Query parameter 'q' is required"}), 400

        api_key = settings.get("weather", "api_key", default="")
        if not api_key:
            return jsonify({"success": False, "results": [], "error": "OpenWeather API key not configured"}), 400

        import urllib.parse
        import urllib.request
        encoded_q = urllib.parse.quote(query)
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={encoded_q}&limit=5&appid={api_key}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "G4Cast/2.1"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    results = []
                    for item in data:
                        results.append({
                            "name": item.get("name"),
                            "state": item.get("state", ""),
                            "country": item.get("country", ""),
                            "lat": round(item.get("lat", 0.0), 4),
                            "lon": round(item.get("lon", 0.0), 4),
                        })
                    return jsonify({"success": True, "results": results})
                else:
                    return jsonify({"success": False, "results": [], "error": f"API returned status {response.status}"}), 502
        except Exception as e:
            logger.error("Location search error: %s", e)
            return jsonify({"success": False, "results": [], "error": str(e)}), 500

    return app

def start_web_server(host: str = "0.0.0.0", port: int = 8080):
    """Start Flask web server in a background daemon thread."""
    app = create_app()
    # Disable werkzeug access logs to keep terminal quiet
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)

    t = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True),
        name="WebServerThread",
        daemon=True
    )
    t.start()
    logger.info("Local G4Cast Web Control Panel listening at http://%s:%d", host, port)
    return t

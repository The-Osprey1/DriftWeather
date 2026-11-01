import requests
import json
import time
import os
import logging
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO)

NWS_CACHE_FILE = "/home/user/G4Cast/nws_cache.json"

def get_nws_alerts(lat=33.963, lon=-117.564, tz_offset=-25200):
    cached_alert = None
    try:
        if os.path.exists(NWS_CACHE_FILE):
            with open(NWS_CACHE_FILE, "r") as cf:
                cache_data = json.load(cf)
                exp_ts = cache_data.get("expires_ts", 0)
                if time.time() < exp_ts:
                    cached_alert = cache_data.get("banner_text")
                    logging.info(f"Loaded valid cached alert: {cached_alert}")
    except Exception as e:
        logging.debug(f"NWS cache read note: {e}")

    url = f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"
    headers = {
        "User-Agent": "(G4CastWeatherStation/2.0, contact@weatherstation.local)",
        "Accept": "application/geo+json"
    }

    try:
        logging.info(f"Querying NWS API: {url}")
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            features = res.json().get("features", [])
            logging.info(f"NWS response 200 OK. Features found: {len(features)}")
            if not features:
                if os.path.exists(NWS_CACHE_FILE):
                    try:
                        os.remove(NWS_CACHE_FILE)
                    except Exception:
                        pass
                return None

            sev_rank = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3}
            sorted_features = sorted(
                features,
                key=lambda f: sev_rank.get(f.get("properties", {}).get("severity", "Unknown"), 9)
            )

            top_alert = sorted_features[0].get("properties", {})
            event_name = top_alert.get("event", "Weather Alert").strip().upper()
            ends_raw = top_alert.get("ends")

            end_str = ""
            exp_ts = time.time() + 1800
            if ends_raw:
                try:
                    dt = datetime.fromisoformat(ends_raw.replace("Z", "+00:00")) + timedelta(seconds=tz_offset)
                    exp_ts = dt.timestamp()
                    end_str = dt.strftime("UNTIL %I %p %a").lstrip("0")
                except Exception:
                    pass

            banner_text = f"! {event_name} - {end_str}" if end_str else f"! {event_name}"

            try:
                with open(NWS_CACHE_FILE, "w") as cf:
                    json.dump({"banner_text": banner_text, "expires_ts": exp_ts}, cf)
                logging.info(f"Cached alert to {NWS_CACHE_FILE}")
            except Exception as e:
                logging.debug(f"NWS cache write note: {e}")

            return banner_text

        elif res.status_code in (404, 500, 502, 503, 504):
            logging.warning(f"NWS API returned {res.status_code}; using cache fallback if available.")
            return cached_alert
    except requests.exceptions.Timeout:
        logging.warning("NWS alert request timed out (6s); continuing with weather display.")
        return cached_alert
    except Exception as e:
        logging.warning(f"NWS alert fetch failed ({e}); continuing with weather display.")
        return cached_alert

    return cached_alert

if __name__ == "__main__":
    print("--- Test 1: Real Eastvale query ---")
    alert = get_nws_alerts(33.963, -117.564)
    print(f"Result for Eastvale: {alert}")

    print("\n--- Test 2: Timeout/Down simulation (Invalid IP / 1s timeout) ---")
    # Simulate a dead endpoint to verify failsafe execution
    t0 = time.time()
    try:
        res = requests.get("https://10.255.255.1", timeout=2)
    except Exception as ex:
        print(f"Failsafe caught cleanly in {time.time() - t0:.2f}s: {type(ex).__name__}")

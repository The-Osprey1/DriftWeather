import requests
import json

# Eastvale, CA coordinates
LAT = 33.963
LON = -117.564

url = "https://api.weather.gov/alerts/active?area=CA"
headers = {
    "User-Agent": "(G4CastWeatherStation, devyn@weather.local)",
    "Accept": "application/geo+json"
}

try:
    resp = requests.get(url, headers=headers, timeout=10)
    print("Status code:", resp.status_code)
    data = resp.json()
    features = data.get("features", [])
    print(f"Active alerts found: {len(features)}")
    for f in features:
        props = f.get("properties", {})
        event = props.get("event")
        headline = props.get("headline")
        severity = props.get("severity")
        urgency = props.get("urgency")
        print(f" - [{severity}] {event}: {headline}")
except Exception as e:
    print("Error:", e)

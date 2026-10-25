import requests
import json

url = "http://api.openweathermap.org/data/2.5/air_pollution"
params = {
    "lat": 33.963,
    "lon": -117.564,
    "appid": "03e1c360794791f241cdd9630f0df7fb"
}

try:
    res = requests.get(url, params=params, timeout=5)
    print("Status:", res.status_code)
    data = res.json()
    item = data.get("list", [{}])[0]
    aqi_index = item.get("main", {}).get("aqi", 1)
    components = item.get("components", {})
    pm25 = components.get("pm2_5", 0)
    
    aqi_labels = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
    label = aqi_labels.get(aqi_index, "Unknown")
    
    print(f"AQI Index: {aqi_index} ({label})")
    print(f"PM2.5: {pm25} ug/m3")
    print(f"Ozone (O3): {components.get('o3')} ug/m3")
except Exception as e:
    print("Error:", e)

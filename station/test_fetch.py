import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Load config
config = {}
with open("/boot/firmware/G4Cast/G4CastData.txt") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            config[k.strip()] = v.strip()

city = config.get("CITY", "Eastvale, US")
api_key = config.get("API_KEY", "")
use_metric = config.get("USE_METRIC", "False").lower() in ("true", "1", "yes")
use_24h = config.get("USE_24HFORMAT", "False").lower() in ("true", "1", "yes")
dark_mode = config.get("DARK_MODE", "False").lower() in ("true", "1", "yes")

# Fetch or cache weather data
cache_file = "/home/user/G4Cast/weather_cache.json"
try:
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            data = json.load(f)
            current_data = data["current"]
            forecast_data = data["forecast"]
    else:
        raise Exception("fetch")
except:
    w_res = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}").json()
    f_res = requests.get(f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}").json()
    with open(cache_file, "w") as f:
        json.dump({"current": w_res, "forecast": f_res}, f)
    current_data = w_res
    forecast_data = f_res

print("Weather fetched successfully:", current_data.get("name"))
print("Current temp (K):", current_data["main"]["temp"])

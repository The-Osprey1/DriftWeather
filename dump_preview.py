import json
from G4Cast import draw_forecast, get_aqi_data

with open("/home/user/G4Cast/weather_cache.json") as f:
    data = json.load(f)

f_data = data["forecast"]
c_data = data["current"]

coords = c_data.get("coord", {})
aqi = get_aqi_data(coords.get("lat", 33.963), coords.get("lon", -117.564))

img = draw_forecast(f_data, c_data, aqi_text=aqi)
img.save("/home/user/G4Cast/preview_aqi.png")
print("Saved preview_aqi.png successfully with AQI:", aqi)

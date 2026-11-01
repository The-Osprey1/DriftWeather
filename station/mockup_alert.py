import json
from PIL import Image, ImageDraw
import numpy as np
from G4Cast import draw_forecast, load_font, text_size, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_FG, COLOR_BG

with open("/home/user/G4Cast/weather_cache.json") as f:
    data = json.load(f)

img = draw_forecast(data["forecast"], data["current"])
draw = ImageDraw.Draw(img)

# --- MOCKUP A: Inverted Alert Pill across bottom of Graph Card ---
# Graph card is at x0=262, y0=170, x1=784, y1=468
pill_x0 = 262 + 20
pill_x1 = 784 - 20
pill_y0 = 468 - 32
pill_y1 = 468 - 8

# Fill inverted black pill badge
draw.rounded_rectangle([pill_x0, pill_y0, pill_x1, pill_y1], radius=6, fill=COLOR_FG)
f_alert = load_font(13, "bold")
alert_text = "! EXCESSIVE HEAT WARNING - IN EFFECT UNTIL 8 PM MON"
tw, th = text_size(draw, alert_text, f_alert)
draw.text(((pill_x0 + pill_x1) // 2 - tw // 2, (pill_y0 + pill_y1) // 2 - th // 2 - 1), alert_text, font=f_alert, fill=COLOR_BG)

img.save("/home/user/G4Cast/preview_alert_banner.png")
print("Saved preview_alert_banner.png")

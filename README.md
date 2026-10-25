# 🌦️ DriftWeather — 32×8 Matrix Weather & Astronomical Station

An intelligent, low-glance desktop meteorological station and astronomical ephemeris display built for 32×8 RGB LED matrices (ESP32 / AWTRIX NG).

Combines ultra-lightweight embedded Berry apps (`.ax`) running natively on ESP32 microcontrollers with autonomous PC-side Python daemons that push animated weather jewels, air quality alerts, and real-time solar daylight arcs.

---

## 🎨 Visual Showcase & Features

| Mode / App | Display Preview | Description | Tech / Algorithm |
| :--- | :---: | :--- | :--- |
| **Jewelbox Weather Brief** | `[ ☀️  78°F CLEAR SKY ]` | 8×8 animated weather condition jewel + 23×8 high-legibility glance lane with 6h hazard scoring. | Open-Meteo API, WMO hazard priority tie-breaker |
| **Jewelbox AQI Brief** | `[ 🌬️  AQI 32  GOOD ]` | Flowing-wind animated jewel with EPA air quality color bands and live PM2.5/PM10 readings. | CAMS ENSEMBLE air quality forecast |
| **Meridian Solar Ribbon** | `[  . * ^ * .  14:30 ]` | 24-hour day ribbon across 32 columns (45 min/col) tracing the sun's physical altitude arc, twilights, and a vertical "now" light shaft. | NOAA Solar Equations, local solar geometry |
| **Sunset Descent (v3.1)** | `[ 🌅  SUNSET IN 18m ]` | Live sunset descent with 3-stop sky gradient, dithered atmospheric burn, and two counter-drifting cloud decks lit from underneath. | Solar raycasting, 3-stop gamma 2.2 dither |
| **Moon Ephemeris (v2.1)** | `[ 🌔  WAXING  82% ]` | Astronomical moon phase with illuminated fraction, real terminator curve, earthshine, and eclipse detection. | Jean Meeus Ch. 48 phase angle ephemeris |
| **Timepiece** | `[ 12:45  SPLIT-FLAP ]` | Bold daypart clock with smooth split-flap minute roll and a sweeping seconds horizon line. | Native ESP32 NTP sync, proportional typography |
| **Nightkeeper** | `[ 🌙  BEDTIME FADE ]` | Circadian bedtime fade, automated blackout, and gentle morning wake transitions. | Perceptual gamma ramp, hardware display power control |

---

## 📁 Repository Layout

```
WeatherStation/
├── weather/                     # Core weather suite (Berry scripts, Python senders & tests)
│   ├── aqi.ax                   # Berry on-device US AQI app with breathing lungs animation
│   ├── aqi_brief_preview.py     # AQI brief visual preview generator
│   ├── aqi_brief_push.py        # Autonomous AQI brief push daemon
│   ├── berry_lite.py            # Fast Python in-memory Berry runtime simulator
│   ├── capture_panel.py         # Screenshot utility for AWTRIX displays
│   ├── minify_ax.py             # Deterministic Berry script minifier for tight ESP32 heaps
│   ├── moon-panel.ax            # v2.1 advanced Moon phase tracker (nebula, earthshine, eclipses)
│   ├── moon-panel-v2.0.ax       # v2.0 Moon phase tracker rollback baseline
│   ├── moon.ax                  # Lightweight standalone 8x8 moon phase module
│   ├── moon_panel_sim.py        # Python simulation model for Moon tracker
│   ├── preview_countdown.py     # Terminal preview for countdown hourglass
│   ├── preview_moon.py          # Terminal preview for moon phase icons
│   ├── preview_sunset.py        # Terminal preview for sunset sky wash and descent
│   ├── soon.ax                  # Target countdown with settling hourglass animation
│   ├── sunset.ax                # v3.1 self-contained Sunset descent app
│   ├── test_*.py                # 240+ automated unit & contract tests
│   ├── weather_brief_preview.py # Weather brief visual preview generator
│   ├── weather_brief_push.py    # Autonomous Weather Brief push daemon
│   ├── weather_canvas.py        # Drawing primitives & 32x8 frame buffer
│   ├── weather_icons.py         # 8x8 weather icon library & palettes
│   ├── wx.ax                    # Shared Berry module: weather icons, temp tints, condition categories
│   ├── wxfeed.ax                # Headless Berry feed aggregator & 6h hazard prioritization
│   ├── wxnow.ax                 # Real-time condition & temp with day/night icon
│   ├── wxrange.ax               # High/low temperature range display
│   ├── wxsky.ax                 # Cloud cover and sky conditions display
│   └── wxsun.ax                 # Sunrise & sunset display with atmospheric sky tint
├── hardware/                    # 3D models, CAD designs & schematics
│   ├── AWTRIX3-M-1.3mf          # Full 3D enclosure for 32x8 matrix display
│   ├── Clock Stand.3mf          # Desktop angled stand 3MF
│   ├── Clock Stand.step         # Parametric STEP CAD model for clock stand
│   └── SCHEMATICS.md            # Hardware BOM, wiring schematics & electrical specs
├── docs/                        # Architecture & design specifications
│   ├── ARCHITECTURE.md          # Dual-mode architecture, memory rules, and algorithms
│   └── sunset-design-qa.md      # Sunset v3.0 redesign QA, cloud physics, and dither analysis
├── config/                      # Firmware & device backups
│   ├── firmware-awtrix-ng.bin   # Verified ESP32 AWTRIX NG 1.1.2 firmware backup
│   ├── pixelclock_apps.json     # App loop configuration backup
│   ├── pixelclock_device.json   # Device calibration & hardware snapshot
│   └── pixelclock_settings.json # Display settings, auto-transitions & brightness
├── visual_system.py             # Gamma 2.2 color tokens, proportional typography & glance lane
├── panel_gate.py                # Process-safe hardware lock & heap-decay protection
├── meridian_push.py             # NOAA solar arc & day ribbon push service
├── meridian_preview.py          # NOAA solar geometry calculations & ribbon renderer
├── test_meridian.py             # Comprehensive test suite for solar day ribbon
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Pytest & package configuration
├── LICENSE                      # MIT License
└── .gitignore
```

---

## 🔌 Hardware Assembly & Schematics

Full electrical details and Bill of Materials are available in [`hardware/SCHEMATICS.md`](hardware/SCHEMATICS.md).

### Quick Pinout Mapping

| Component | Pin (ESP32) | Mode | Notes |
| :--- | :---: | :---: | :--- |
| **LED Matrix DIN** | **GPIO 32** | Output | Series 330Ω–470Ω resistor recommended |
| **Matrix Power (+5V)** | **5V / VIN** | Power | Connect to 5V ≥ 2A supply (with 1000 µF cap across 5V/GND) |
| **Common Ground** | **GND** | Ground | Must tie ESP32 and Matrix ground together |
| **Ambient Light Sensor** | **GPIO 35** | Analog | LDR + 10kΩ divider for auto-brightness dimming |
| **Left / OK / Right Buttons**| **GPIO 26 / 27 / 14**| Input | Tactile momentary push buttons (Active LOW) |
| **Piezo Buzzer** | **GPIO 15** | PWM | Audible hazard alerts |

### 3D Printable Enclosure & Stand

Production-ready 3D models are located in `hardware/`:
- **`AWTRIX3-M-1.3mf`**: Complete snap-together enclosure for the 32×8 matrix and ESP32 board.
- **`Clock Stand.3mf`** & **`Clock Stand.step`**: Desktop angled stand for viewing on desks or nightstands.

---

## 🚀 Quickstart & Setup

### 1. Python Environment Setup

```bash
git clone https://github.com/The-Osprey1/DriftWeather.git
cd DriftWeather

# Install required dependencies
pip install -r requirements.txt
```

### 2. Run Autonomous Push Daemons

#### Weather Brief (Jewelbox):
```bash
# Dry run once (no panel writes):
python weather/weather_brief_push.py --dry-run --once

# Run daemon continuously:
python weather/weather_brief_push.py
```

#### Air Quality Brief:
```bash
# Dry run once:
python weather/aqi_brief_push.py --dry-run --once

# Run daemon continuously:
python weather/aqi_brief_push.py
```

#### Meridian Solar Arc:
```bash
# Dry run once:
python meridian_push.py --dry-run --once

# Run continuously:
python meridian_push.py
```

---

## ⚡ Deploying On-Device Berry Scripts

For standalone operation without a host PC, apps can be uploaded directly to the AWTRIX NG panel via HTTP:

```bash
# 1. Minify script before uploading (essential for tight ESP32 RAM)
python weather/minify_ax.py weather/sunset.ax weather/sunset.min.ax

# 2. Upload to panel over LAN
curl -X POST -F "file=@weather/sunset.min.ax" http://<PANEL_IP>/api/v1/apps/script/sunset
```

---

## 🧪 Automated Test Suite

The repository includes a comprehensive 274+ test suite covering astronomical ephemeris models, NOAA solar geometry, hazard tie-breakers, and visual rendering integrity:

```bash
# Run the complete test suite
pytest

# Run specifically weather logic tests
pytest weather/test_weather_logic.py weather/test_sunset_logic.py
```

---

## 📜 License & Credits

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

* **Author**: Devyn Fidel ([@The-Osprey1](https://github.com/The-Osprey1))
* **Co-Authors & Contributors**: Claude, Codex
* **Data Sources**: [Open-Meteo.com](https://open-meteo.com) (Forecasts), Copernicus Atmosphere Monitoring Service ([CAMS](https://atmosphere.copernicus.eu/)) (Air Quality), NOAA Solar Calculator (Day ribbon ephemeris).

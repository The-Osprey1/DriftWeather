# System Architecture & Technical Specifications

The Weather Station combines autonomous embedded Berry firmware apps running natively on an ESP32 microcontroller with intelligent PC-side background daemons that push rich meteorological and solar timelines.

---

## 🏛️ Architecture Overview

```
                      +------------------------------------------+
                      |         External Weather APIs            |
                      |  Open-Meteo Forecast, CAMS Air Quality   |
                      +--------------------+---------------------+
                                           |
                                  HTTPS    | HTTP (plain)
                                           v
      +------------------------------------+------------------------------------+
      |                                                                         |
      v                                                                         v
+-------------------------------+                       +-------------------------------+
|       PC-Side Services        |                       |   Embedded Berry Firmware     |
|   (Python 3.11+ Daemons)      |                       |     (AWTRIX NG on ESP32)      |
+-------------------------------+                       +-------------------------------+
| • weather_brief_push.py       |                       | • wx.ax (Icons, tints, blit)  |
| • aqi_brief_push.py           |                       | • wxfeed.ax (Headless ingest) |
| • meridian_push.py (NOAA Arc) |                       | • wxnow.ax / wxrange.ax       |
| • visual_system.py (Gamma 2.2)|                       | • sunset.ax (v3.1 sky descent)|
| • panel_gate.py (Heap safety) |                       | • moon-panel.ax (v2.1 Meeus)  |
+---------------+---------------+                       +---------------+---------------+
                |                                                       |
                | PUT /api/v1/apps/pushed/{name}                        | Native SPI/I2C
                +------------------------------>+<----------------------+
                                                |
                                                v
                                    +-----------------------+
                                    |     32x8 WS2812B      |
                                    |     RGB LED Matrix    |
                                    +-----------------------+
```

---

## 💾 Embedded Memory & Heap Safety Rules

AWTRIX NG on the ESP32 runs a shared Berry VM heap (`scriptHeapBudgetBytes: 98304`).

1. **The Contiguous Block Bottleneck**:
   - Total free heap is rarely the limiting factor. The **largest contiguous free block** (`largestFreeBlockBytes`) determines whether an app installs, whether a network buffer allocates, or whether a push survives.
   - On boot, the block starts around ~65–75 KB. As scripts initialize, tables allocate, and memory fragments, the block decays to ~18–25 KB.
2. **Minification & Direct Compiles**:
   - Compiling Berry source on-device requires ~3.5× the file size in contiguous heap.
   - All `.ax` scripts must be minified using `weather/minify_ax.py` prior to installation on the device.
3. **Hardware Gate (`panel_gate.py`)**:
   - Serializes concurrent PC writes via file locks.
   - Enforces rate-limiting gaps between HTTP requests.
   - Prevents memory exhaustion panics by monitoring `/api/v1/system` before pushes.

---

## 🌦️ Astronomical & Meteorological Models

### 1. Lunar Ephemeris (`moon-panel.ax` & `moon_panel_sim.py`)
- Implements Jean Meeus' *Astronomical Algorithms* Chapter 48 phase angle calculation.
- Renders true terminators with earthshine (reflection of sunlight from Earth onto the unlit lunar surface).
- Accounts for lunar eclipses by shifting limb colors across atmospheric blood-red gradients.

### 2. Solar Day Ribbon (`meridian_preview.py` & `meridian_push.py`)
- Based on NOAA Solar Calculator equations.
- Computes exact solar altitude, solar noon, sunrise, and sunset from latitude, longitude, and day of year.
- Maps 24 hours across 32 matrix columns (45 minutes per column), rendering solar altitude as a physical arc across the sky.

### 3. Open-Meteo Hazard Priority Scoring (`wxfeed.ax` & `weather_brief_push.py`)
- Evaluates 6-hour forecast windows across precipitation, extreme temperatures, high winds, and severe storms.
- Employs a deterministic tie-breaker matrix: higher hazard severity takes precedence; ties resolve to the earliest expected event.

---

## 🎨 Visual System & Color Science (`visual_system.py`)

- **Gamma 2.2 Correction**: LED brightness does not scale linearly with human perception. Color transitions and atmospheric sky fades are gamma-corrected to eliminate banding.
- **Low-Brightness Contrast Guard**: Enforces minimum dominant channel values (>= 174) so icons and numerals remain crisp and legible even when panel brightness is dimmed to 1–5%.
- **Glance-Lane Layout**:
  - `x = 0..7`: 8×8 Icon well (animated weather jewel or astronomical icon).
  - `x = 8`: Gutter (kept dark or utilized for status pips).
  - `x = 9..31`: 23×8 Calm-glance proportional typography anchored on row `y = 6`.

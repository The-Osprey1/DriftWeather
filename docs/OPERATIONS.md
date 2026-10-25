# G4Cast Operations & Administration Guide

This guide provides complete operational procedures, architecture details, and troubleshooting steps for the **G4Cast E-Paper Weather Station** (Waveshare 7.5" V2, Raspberry Pi Zero 2 W).

---

## 1. Architecture Overview

G4Cast runs on Raspberry Pi OS with an **OverlayFS read-only root** to protect the microSD card from corruption during power cuts.

```text
G4Cast/
├── config/
│   ├── default_settings.json   # Factory defaults
│   ├── settings.json           # Active configuration (persisted to /media/root-ro)
│   └── settings.py             # Thread-safe settings manager with OverlayFS sync
│
├── display/
│   ├── renderer.py             # 800x480 PIL 1-bit monochrome rendering engine
│   └── epaper.py               # Waveshare 7.5" V2 hardware abstraction & partial updates
│
├── weather/
│   ├── providers.py            # OpenWeather (Current, Forecast, AQI), NOAA KCNO, NWS Alerts
│   ├── cache.py                # Multi-tier caching with subtle freshness formatting
│   └── updater.py              # Update coordinator with failsafe fallbacks & listeners
│
├── services/
│   ├── wifi_watchdog.py        # Self-healing Wi-Fi watchdog (HTTP/ICMP/link probes)
│   ├── scheduler.py            # Master scheduler: 30m weather sync, 1m clock, quiet hours
│   └── health.py               # Hardware telemetry (CPU temp, RAM, Disk, RSSI, Uptime)
│
├── web/
│   ├── server.py               # Flask REST API server (port 8080)
│   ├── templates/index.html    # Responsive dark-mode control panel
│   └── static/style.css        # Minimalist responsive stylesheet
│
├── main.py                     # Unified master runner
├── G4Cast.py                   # Backward-compatible entrypoint for systemd
└── run_all.sh                  # Boot script executing Wi-Fi check & G4Cast
```

---

## 2. Web Control Panel (http://<pi-ip>:8080)

Connect any phone, tablet, or computer to your local Wi-Fi and navigate to:
`http://192.168.1.65:8080`

### Key Features:
- **Live Display Preview Mirror**: View the exact 800x480 screen buffer rendered in real time.
- **One-Click Refresh**: Forces an immediate live weather fetch and screen update.
- **One-Click Clean**: Runs an alternating white/black deep waveform cycle to purge residual e-paper ghosting.
- **Visual Mode**: Toggle between `Off (Always Light)`, `On (Always Dark)`, or `Auto (Solar: Sunset -> Sunrise)`.
- **Location Search**: Look up any city or coordinates worldwide using OpenWeather Geocoding.
- **Severe Weather Simulation**: Test how NWS Flash Flood, High Wind, or Heat warnings display on screen.
- **Configuration Backup & Restore**: One-click download of your configuration (`g4cast_settings.json`) or upload a JSON backup to restore settings across reboots.

---

## 3. Wi-Fi Watchdog & Self-Healing Network

A weather station should recover automatically after router reboots or temporary outages:
1. **Lightweight Probes**: Tests HTTP `generate_204` endpoints and ICMP ping every 30 seconds.
2. **Interface Verification**: Validates interface link association (`iwgetid`) to prevent false-offline loops.
3. **Progressive Recovery**:
   - Outage < 90s: Retries silently without tearing down connections.
   - Outage > 90s: Triggers non-disruptive `nmcli connection up`.
   - Outage > 4m: Restarts `NetworkManager` as an extreme fallback.
4. **Immediate Post-Recovery Refresh**: The instant connectivity returns, G4Cast immediately updates weather data and wakes the display.

---

## 4. Solar Auto-Switching & Dark Mode

- **3-Way Modes**:
  - `off`: Standard light mode (black ink on paper-white background).
  - `on`: Inverted dark mode (white ink on deep black background).
  - `auto`: Dynamically calculates local sunrise and sunset from weather data. When between sunset and sunrise, dark mode is enabled automatically.
- **Anti-Aliasing & Thresholding**:
  - Light mode uses threshold `150` for sharp text and fine curves.
  - Dark mode uses threshold `105` to prevent erosion of fine white glyphs and numbers against black.

---

## 5. Air Quality Index (AQI)

- Fetches real-time PM2.5, PM10, ozone, and CO from OpenWeather's Air Pollution API.
- Renders an elegant, non-disruptive pill badge (`AQI: Good`, `AQI: Moderate`, or numerical AQI) in the top-right header of the 24-hour graph.
- Preserves cached AQI during intermittent network drops.

---

## 6. OverlayFS & Persistent Storage

Because Raspberry Pi OS runs with OverlayFS read-only protection:
- Settings edits in the web panel write to `/home/user/G4Cast/config/settings.json` in RAM.
- A transparent background worker synchronizes this file to the underlying microSD card:
  `sudo mount -o remount,rw /media/root-ro && sudo cp /home/user/G4Cast/config/settings.json /media/root-ro/home/user/G4Cast/config/settings.json && sudo mount -o remount,ro /media/root-ro`
- Your settings survive power cuts, hard reboots, and OS updates.

---

## 7. System Administration & Commands

### Managing the Service
- Check service status: `sudo systemctl status G4Cast.service`
- View live service logs: `journalctl -u G4Cast.service -f`
- Restart service: `sudo systemctl restart G4Cast.service`
- Stop service: `sudo systemctl stop G4Cast.service`

### Manual Backup Creation
Run the included backup script on the Pi:
`python3 create_backup.py`
This saves a complete timestamped `.tar.gz` archive of your configuration and assets to `/home/user/backups/`.

### Headless Wi-Fi Provisioning
To configure a new Wi-Fi network without SSH access:
1. Power off the Pi and insert the microSD card into a computer.
2. Open the `boot` partition (accessible on Windows and Mac).
3. Edit or create `G4Cast/Wifi.txt`:
   ```ini
   ssid=YourNetworkName
   psk=YourNetworkPassword
   ```
4. Eject and boot the Pi. `ConnectWifi.py` connects automatically at boot.

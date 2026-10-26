# G4Cast E-Paper Weather Station (React & TypeScript)

A modern, high-contrast Web Control Panel and pixel-perfect 800×480 Waveshare 7.5" V2 monochrome e-paper display simulator for the G4Cast weather station.

## Architecture & Features

### 1. Live 800×480 E-Paper Display Mirror & Simulator
- **Pixel-Accurate 800×480 E-Paper Canvas**: Accurate reproduction of Waveshare 7.5" V2 1-bit monochrome electrophoretic display.
- **Waveform Refresh & Clean Simulation**: Realistic multi-phase black/white inversion flashes mimicking physical e-paper electrophoretic microcapsules when refreshing or performing a deep ghosting clean.
- **4 Visual Layout Styles**:
  - **Classic**: Floating spline graph, balanced hero temperature card, subtle vertical guidelines, and daily forecast columns.
  - **Widgets**: Modular 2×2 metric tiles (Humidity, Wind, UV, Pressure), upper digital clock, and shaded trend graph.
  - **Dual-Tone**: High-contrast solid inverted hero card with white typography on deep black.
  - **Minimalist**: Nordic editorial layout with corner registration marks and tactile chiclet keycap forecast columns.
- **Temperature Glanceability Sizing**:
  - Compact (54pt), Standard (68pt), Large (82pt).
- **Dark Mode & Solar Auto-Switching Engine**:
  - "Off" (Light / paper mode)
  - "On" (Dark / inverted mode)
  - "Auto" (Astronomical NOAA solar calculations automatically switching between day and night based on local coordinates).
- **Monochrome AQI Pill Badge**: Real-time Air Quality Index badge situated at top-right of the 24-hour graph header ([676..764, 162..184]).
- **Severe Weather Alert Banner**: High-contrast inverted warning banner at `y=436` with collision-safe PoP badge suppression.

### 2. Comprehensive 7-Tab Control Panel
1. **Weather**: City & country, display name, interactive location search with geocoding, OpenWeather API key, NOAA ground station sensor (KCNO), and metric/imperial toggle.
2. **Display**: 24-hour clock toggle, visual mode (off/on/auto), 0° / 180° panel rotation, and full refresh cycle interval.
3. **Customization**: Interactive dashboard visual layout cards with previews (Classic, Widgets, Dual-Tone, Minimalist) and temperature glanceability sizing.
4. **Schedule**: Bedroom quiet hours window (start & end time) with override for severe weather alerts.
5. **Network**: Wi-Fi watchdog self-healing toggle, liveness ping host, SSID, IP address, and reconnect trigger.
6. **Diagnostics**: Real-time telemetry: CPU temperature, system uptime, memory usage, disk free space, Wi-Fi signal dBm, sync status, and refresh counter.
7. **Tools & Backup**: Severe weather alert simulations (Wind Warning, Flood Watch, Heat Warning, custom title), configuration JSON export download, and schema-validated JSON import.

## Getting Started

```bash
# Install dependencies
npm install

# Start the dev server on port 3000
npm run dev

# Build production bundle
npm run build
```

## Technology Stack
- **Framework**: React 18 with TypeScript
- **Styling**: Tailwind CSS & G4Cast design system
- **Build Tool**: Vite 6
- **Icons**: Lucide React / SVG

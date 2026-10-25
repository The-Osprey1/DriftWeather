# Original User Request

## Initial Request — 2026-09-14T05:39:31Z

Implement and deploy a comprehensive feature expansion and operational runbook for the G4Cast 800×480 E-Paper weather station (Waveshare 7.5" V2, Raspberry Pi Zero 2 W).

Working directory: C:\Users\devyn\.gemini\antigravity\scratch\G4Cast
Integrity mode: development

## Requirements

### R1. Air Quality Index (AQI) Integration
Integrate real-time Air Quality Index data into the weather pipeline. Fetch AQI from OpenWeather's Air Pollution API (or station observation fallback) and render a high-contrast monochrome AQI pill badge (`AQI: Good`, `AQI: Moderate`, or numerical value) in the designated card area without disrupting existing typography, curves, or dividers.

### R2. Dark Mode & Solar Auto-Switching
Provide a robust Dark Mode (inverted 1-bit monochrome palette: white text/curves on deep black canvas) that preserves sharp edge contrast. Support three modes: `Off` (always light), `On` (always dark), and `Auto` (switches to Dark Mode between local sunset and sunrise calculated from the weather data). Expose theme controls in the web portal and settings file.

### R3. Severe Weather Alert Banner & Simulation Testing
Enhance the National Weather Service (NWS) alert system to render a prominent high-contrast banner when active watches/warnings are detected. Add an alert simulation endpoint and UI button in the web control panel allowing users to test and preview simulated alert layouts (e.g. Flash Flood Watch, High Wind Warning) directly on the display preview mirror.

### R4. Web Portal Configuration Backup, Restore & Search
Extend the local Flask web control panel (`port 8080`):
- Add a one-click "Export Configuration" button to download `settings.json`.
- Add an "Import Configuration" file upload feature with schema validation that immediately saves and synchronizes persistently to the underlying SD card `/media/root-ro`.
- Add an interactive location/timezone search helper in the settings panel.

### R5. Complete Documentation & Long-Term Operational Guide
Create a polished, comprehensive `README.md` and `docs/OPERATIONS.md` in the repository documenting:
- Architecture overview and module breakdown.
- Local Web Control Panel guide (`http://<pi-ip>:8080`).
- Wi-Fi configuration and headless recovery procedures.
- Quiet hours scheduling and e-paper maintenance/cleaning cycle details.
- Physical Raspberry Pi Zero 2 W deployment, systemd management, and OverlayFS persistence mechanics.

## Acceptance Criteria

### Functionality & Code Quality
- [ ] AQI data is fetched periodically with silent cache fallback when offline, and renders cleanly on the 800×480 canvas.
- [ ] Dark Mode generates a crisp 1-bit monochrome image with 0 anti-aliasing artifacts or inverted ghosting.
- [ ] Solar auto-switching transitions accurately between light and dark modes according to sunrise/sunset timestamps.
- [ ] NWS alert banner renders legibly without overlapping existing temperature text or the 24-hour forecast curve.
- [ ] Web portal allows testing simulated alerts and updates the live preview mirror immediately.
- [ ] Config export produces a valid JSON file, and config import validates structure before persisting to `/media/root-ro`.
- [ ] All 11 refined layout coordinates remain intact during normal conditions.
- [ ] Test scripts pass without regressions, and deployment script deploys clean code to the Pi (`192.168.1.65`).

### Verification Resources
- Verification scripts: `python -m unittest` or dedicated validation scripts testing PIL rendering, settings persistence, and API routes.
- Live verification: Pi hardware at `192.168.1.65` responds on port 8080 with 200 OK across `/api/status`, `/api/diagnostics`, `/api/preview.png`, and new backup/restore endpoints.

## Follow-up — 2026-09-14T18:22:06Z

The server has restarted. Please resume the project coordination from your current checkpoint (Milestone 2: Dark Mode & Solar Auto-Switching through Milestone 6). All prior deliverables and PROJECT.md remain intact. Continue driving the milestones forward to completion.


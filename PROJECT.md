# Project: G4Cast 800x480 E-Paper Weather Station Feature Expansion

## Architecture
G4Cast is a Python-based weather station running on a Raspberry Pi Zero 2 W with a Waveshare 7.5" V2 (800x480) 1-bit monochrome e-paper display and an OverlayFS read-only root filesystem with `/media/root-ro` persistence.

The software architecture consists of:
- **Display Pipeline** (`display/renderer.py`, `display/epaper.py`): PIL-based 800x480 1-bit monochrome canvas generation, font loading, layout coordinates, curve plotting, 1-bit thresholding, and Waveshare SPI driver integration.
- **Weather Pipeline** (`weather/providers.py`, `weather/cache.py`): Multi-provider weather fetching (OpenWeather, NWS, NOAA KCNO METAR, OpenWeather Air Pollution API), caching, and failsafe fallbacks.
- **Solar & Time Services** (`services/`): Sunrise/sunset auto-switching calculation (local time-of-day normalized comparison and astronomical offline solar engine), scheduler daemon, quiet hours management.
- **Web Control Panel** (`web/server.py`, `web/templates/index.html`, port 8080): Flask HTTP service exposing live preview mirror (`/api/preview.png`), system status and diagnostics, theme controls, alert simulation, configuration backup/restore, and location search.
- **Configuration & Storage** (`config/settings.py`, `config/settings.json`): Atomic configuration management, schema validation, and OverlayFS persistence to `/media/root-ro`.
- **System Services & Runbook** (`services/`, `docs/OPERATIONS.md`, `README.md`): Systemd service management, backup/recovery runbook, and headless Wi-Fi provisioning.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Air Quality Index Rendering | Render AQI monochrome pill badge in 24-hour graph header without coordinate shift | M1 (DONE) | ORIGINAL_REQUEST §R1 |
| 2 | AQI Data Pipeline & Fallback | Fetch OpenWeather Air Pollution API, compute AQI/PM2.5, persistent cache fallback | M1 (DONE) | ORIGINAL_REQUEST §R1 |
| 3 | 3-Way Dark Mode Settings | Support "off", "on", "auto" modes in settings and web control panel | M2 | ORIGINAL_REQUEST §R2 |
| 4 | Solar Auto-Switching Engine | Normalized time-of-day solar calculation + offline astronomical solar engine | M2 | ORIGINAL_REQUEST §R2 |
| 5 | Symmetrical 1-Bit Thresholding | Dynamic 1-bit PIL binarization (threshold 105 for dark, 150 for light) to prevent glyph erosion | M2 | ORIGINAL_REQUEST §R2 |
| 6 | NWS Alert Banner & Collision Fix | Prominent inverted alert banner with PoP collision suppression at y=436 | M3 | ORIGINAL_REQUEST §R3 |
| 7 | Alert Simulation & Preview UI | Web endpoints (/api/alert/simulate, /api/alert/clear) and UI simulation controls | M3 | ORIGINAL_REQUEST §R3 |
| 8 | Config Export Endpoint & UI | Web endpoint /api/config/export and UI button to download settings.json | M4 | ORIGINAL_REQUEST §R4 |
| 9 | Config Import with Schema Validation | Web endpoint /api/config/import, UI upload, strict schema check & /media/root-ro sync | M4 | ORIGINAL_REQUEST §R4 |
| 10 | Location / Timezone Search Helper | Web endpoint /api/location/search and UI interactive geocoding helper | M4 | ORIGINAL_REQUEST §R4 |
| 11 | Complete Repository Documentation | Comprehensive README.md and docs/OPERATIONS.md operational runbook | M5 | ORIGINAL_REQUEST §R5 |
| 12 | Backup Script Modernization | Update create_backup.py and RESTORE.md for full modular codebase | M5 | ORIGINAL_REQUEST §R5 |
| 13 | Unit & Mock Test Suite | Comprehensive tests/ suite passing under `python -m unittest discover` | M6 | ORIGINAL_REQUEST Acceptance |
| 14 | E2E Verification & Pi Deployment | Deploy to live Pi at 192.168.1.65, commit to /media/root-ro, live verification | M6 | ORIGINAL_REQUEST Acceptance |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: AQI Pipeline & Display | Fetch/cache AQI and render monochrome pill badge at [676..764, 162..184] | none | DONE |
| 2 | M2: Dark Mode & Solar Switching | 3-way modes ("off"/"on"/"auto"), normalized solar calculation, threshold=105 | M1 | IN_PROGRESS |
| 3 | M3: Severe Weather Alert Banner | NWS banner rendering, PoP collision suppression, simulation API & UI | M1 | PLANNED |
| 4 | M4: Web Portal Backup, Restore & Search | Config export, schema-validated import, /media/root-ro persistence, location search | M2, M3 | PLANNED |
| 5 | M5: Documentation & Operations Runbook | README.md, docs/OPERATIONS.md, updated create_backup.py and RESTORE.md | none | PLANNED |
| 6 | M6: Test Suite, Hardware Deployment & Live Verification | Mocked test suite in tests/, deploy to Pi 192.168.1.65, live endpoint verification | M1, M2, M3, M4, M5 | PLANNED |

## Interface Contracts
### Weather Pipeline ↔ Display Renderer
- `display.renderer.WeatherRenderer.render(...)`:
  - Parameter `aqi_text: Optional[str] = None` (e.g. `"AQI: Good"` or `"AQI: 38"`)
  - Parameter `dark_mode: bool = False`
  - Parameter `alert: Optional[Dict[str, Any]] = None`
  - Returns `PIL.Image.Image` (mode "1", size (800, 480))
- Pill Badge Geometry:
  - Top-right of 24-hour graph header: `x0=676, y0=162, x1=764, y1=184`, radius=11.
  - Alert Banner Geometry: `x0=320, y0=436, x1=764, y1=460`, radius=6. When alert active, PoP badges suppressed.

### Settings ↔ Solar Auto-Switching & Web Portal
- Settings schema:
  - `display.dark_mode`: string `"off"` | `"on"` | `"auto"` (legacy bool `true`/`false` automatically normalized to `"on"`/`"off"`).
- Solar Evaluation:
  - Function `services.scheduler.evaluate_dark_mode(mode: str, weather_data: dict, lat: float, lon: float) -> bool`
  - Compares local time-of-day with sunrise and sunset, falls back to astronomical solar calculation.

### Web Server Endpoints
- `GET /api/config/export` -> JSON attachment download of `settings.json`.
- `POST /api/config/import` -> Multipart form file or JSON body, validates schema, persists to OverlayFS (`/media/root-ro`), triggers preview re-render.
- `GET /api/location/search?q=<query>` -> Returns JSON list of matched locations `[{"name": "...", "lat": ..., "lon": ..., "timezone": "..."}]`.
- `POST /api/alert/simulate` -> Injects simulated alert payload into cache, triggers display update.
- `POST /api/alert/clear` -> Clears simulated alert, restores normal display.

## Code Layout
- `display/`: `renderer.py` (PIL rendering, layout coordinates), `epaper.py` (hardware driver).
- `weather/`: `providers.py` (OpenWeather, NWS, KCNO), `cache.py` (JSON caching).
- `config/`: `settings.py` (configuration manager, schema validation, OverlayFS persistence), `settings.json`.
- `web/`: `server.py` (Flask server routes), `templates/index.html` (control panel UI), `static/` (CSS, JS).
- `services/`: `scheduler.py` (update loop, dark mode evaluation).
- `tests/`: `test_renderer.py`, `test_settings.py`, `test_solar.py`, `test_web.py`, `test_aqi.py`.
- `docs/`: `OPERATIONS.md`.
- Root: `README.md`, `create_backup.py`, `RESTORE.md`, `PROJECT.md`.

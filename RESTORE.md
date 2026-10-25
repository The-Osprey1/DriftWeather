# G4Cast Weather Display - Backup & Restore Guide

This backup contains the complete, production-ready configuration and source code for the G4Cast E-Ink Weather Display (Raspberry Pi Zero 2 W with Waveshare 7.5" V2 E-Paper Display).

## Included in this Backup
* `G4Cast.py`: Production weather script featuring:
  * Inter typography & crisp monochrome rendering
  * Dynamic auto-scaling for 3-digit temperatures (100°F+)
  * Context-aware precipitation timeline (rain chance & accumulation bars)
  * Fast waveform refresh (1.78s) with periodic anti-ghosting cycles
  * National Weather Service (NWS) severe weather & heat advisory alerts with failsafes
  * Air Quality Index (AQI) & PM2.5 monitoring
* `fonts/`: Complete Inter font family (Bold, SemiBold, Medium, Regular)
* `pic/`: 1-bit / monochrome weather icons (day/night, rain, snow, clear, clouds, etc.)
* `G4Cast.service`: Systemd service definition for autonomous startup on boot
* `G4CastData.txt`: Configuration file template (City, OpenWeatherMap API Key, units)
* `validate_all.py`: Comprehensive 36-point automated hardware & API test suite

## Quick Restore Instructions on a Fresh Raspberry Pi
1. Flash Raspberry Pi OS Bookworm (Lite 32-bit or 64-bit) to a MicroSD card.
2. Boot Pi, connect to Wi-Fi, and enable SPI:
   ```bash
   sudo raspi-config nonint do_spi 0
   ```
3. Install required packages:
   ```bash
   sudo apt update
   sudo apt install -y python3-pil python3-numpy python3-requests python3-flask python3-gpiozero python3-lgpio fonts-inter
   ```
4. Install Waveshare e-Paper driver:
   ```bash
   git clone https://github.com/waveshare/e-Paper.git
   cd e-Paper/RaspberryPi_JetsonNano/python
   sudo python3 setup.py install
   ```
5. Extract this backup into `/home/user/G4Cast`:
   ```bash
   tar -xzf G4Cast_Backup.tar.gz -C /home/user/
   ```
6. Copy the systemd service and enable it:
   ```bash
   sudo cp /home/user/G4Cast/G4Cast.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now G4Cast.service
   ```

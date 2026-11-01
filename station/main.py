#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast Master Application Runner
Launches Wi-Fi watchdog, local Flask control panel, and master display scheduler.
"""

import sys
import time
import signal
import logging
from pathlib import Path

# Ensure root package directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import get_settings
from services.wifi_watchdog import get_wifi_watchdog
from services.scheduler import get_scheduler
from web.server import start_web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("G4Cast.Main")

def main():
    logger.info("==========================================")
    logger.info("  Starting G4Cast E-Paper Weather Station ")
    logger.info("==========================================")

    settings = get_settings()
    net_cfg = settings.get("network", default={})
    web_cfg = settings.get("web", default={})

    # 1. Start Wi-Fi Watchdog & Self-Healing Service
    watchdog = get_wifi_watchdog(
        check_interval=net_cfg.get("check_interval_seconds", 30),
        ping_host=net_cfg.get("ping_host", "1.1.1.1"),
        max_retries=net_cfg.get("max_reconnect_attempts", 3)
    )
    if net_cfg.get("watchdog_enabled", True):
        watchdog.start()

    # 2. Start Local Web Control Panel (Flask)
    web_host = web_cfg.get("host", "0.0.0.0")
    web_port = web_cfg.get("port", 8080)
    start_web_server(host=web_host, port=web_port)

    # 3. Start Master Display Scheduler
    scheduler = get_scheduler()

    # Signal handlers for graceful systemd termination
    def shutdown_handler(signum, frame):
        logger.info("Received termination signal %d. Shutting down gracefully...", signum)
        scheduler.stop()
        watchdog.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        scheduler.start()
        # Keep main thread alive
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        shutdown_handler(0, None)

if __name__ == "__main__":
    main()

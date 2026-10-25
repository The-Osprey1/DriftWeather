#!/usr/bin/env python3
"""
Setup G4Cast systemd service safely with proper logging, error handling, and permissions.

"""

import os
import sys
import shutil
import subprocess
import stat

# --- CONFIGURATION ---
SERVICE_NAME = "G4Cast.service"  # Name of the systemd service
SERVICE_PATH = f"/etc/systemd/system/{SERVICE_NAME}"  # Full path to service file

# Base directory where this setup script lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Directory for logs (not used anymore in journal mode, but kept for other uses)
LOG_DIR = os.path.join(BASE_DIR, "log")

# Path to the main script that the service will run
SCRIPT_PATH = os.path.join(BASE_DIR, "run_all.sh")

# Find python3 binary path (not directly used here, but useful if needed)
PYTHON_PATH = shutil.which("python3")

# --- ENSURE SCRIPT RUNS AS ROOT ---
if os.geteuid() != 0:
    print("ERROR: This script must be run with sudo")
    sys.exit(1)

# --- CHECK DEPENDENCIES ---
if not PYTHON_PATH:
    print("ERROR: python3 not found in PATH")
    sys.exit(1)

if not os.path.exists(SCRIPT_PATH):
    print(f"ERROR: Script not found at {SCRIPT_PATH}")
    sys.exit(1)

# --- FIX 2: Ensure log directory exists ---
# This prevents any future scripts from failing if they try to write logs
os.makedirs(LOG_DIR, exist_ok=True)

# --- FIX 5: Ensure the main script is executable ---
# Check file permissions and add execute permission if missing
st = os.stat(SCRIPT_PATH)
if not (st.st_mode & stat.S_IXUSR):
    print(f"Making {SCRIPT_PATH} executable")
    os.chmod(SCRIPT_PATH, st.st_mode | stat.S_IXUSR)

# --- FIX 7: Use systemd journal for logging ---
# StandardOutput and StandardError point to the journal instead of files
SERVICE_CONTENT = f"""[Unit]
Description=G4Cast E-Ink Weather Display
After=network-online.target
Wants=network-online.target

[Service]
User=root
WorkingDirectory={BASE_DIR}
ExecStart={SCRIPT_PATH}
Restart=on-failure
RestartSec=10
Environment="PATH=/usr/bin:/usr/local/bin"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

# --- FIX 6: Write service file with proper error handling ---
try:
    with open(SERVICE_PATH, "w") as f:
        f.write(SERVICE_CONTENT)
    print(f"Service file written to {SERVICE_PATH}")
except Exception as e:
    print(f"ERROR: Failed to write service file: {e}")
    sys.exit(1)

# --- FIX 1: Reload systemd and enable/restart service safely using subprocess ---
try:
    # Reload systemd to pick up new service
    subprocess.run(["systemctl", "daemon-reload"], check=True)

    # Enable the service to start at boot
    subprocess.run(["systemctl", "enable", SERVICE_NAME], check=True)

    # Start/restart the service immediately
    subprocess.run(["systemctl", "restart", SERVICE_NAME], check=True)

    print("Service enabled and started successfully.")
    print("Check logs with: journalctl -u G4Cast.service -f")

except subprocess.CalledProcessError as e:
    # Catch errors from systemctl commands
    print(f"ERROR: systemctl command failed: {e}")
    sys.exit(1)

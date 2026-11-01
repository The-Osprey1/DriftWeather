#!/usr/bin/env python3
"""
G4Cast Wi-Fi auto-connect helper

Fixes applied:
1. Connection name is no longer the raw SSID (prevents special-character issues)
2. Hidden SSID support enabled
3. Wifi.txt supports comments (#) and blank lines
"""

import subprocess
import time
import os
import sys
import re

# Base directory on the boot partition where config files live
BASE_DIR = "/boot/firmware/G4Cast"

# File containing Wi-Fi credentials:
#   ssid=YourNetworkName
#   psk=YourPassword
# Comments (#) and blank lines are allowed
WIFI_FILE = os.path.join(BASE_DIR, "Wifi.txt")


def sanitize_name(name):
    """
    Convert SSID into a safe NetworkManager connection name.
    Replaces unsupported characters with '_'.
    """
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


def read_wifi_file(path):
    """
    Read SSID and PSK from a key=value text file, ignoring comments (#) and blank lines.
    Returns (ssid, psk) or (None, None) if missing.
    """
    if not os.path.exists(path):
        print(f"Wi-Fi credentials file {path} not found → exiting", flush=True)
        return None, None

    ssid = None
    psk = None

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # skip blank lines and comments
            if line.startswith("ssid="):
                ssid = line.split("=", 1)[1].strip()
            elif line.startswith("psk="):
                psk = line.split("=", 1)[1].strip()

    return ssid, psk


def wait_for_networkmanager(timeout=60):
    """
    Wait until NetworkManager is fully running.
    """
    print("Waiting for NetworkManager...", flush=True)

    for _ in range(timeout):
        result = subprocess.run(
            ["/usr/bin/nmcli", "-t", "-f", "RUNNING", "general"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )

        if "running" in result.stdout:
            print("NetworkManager is running", flush=True)
            return True

        time.sleep(1)

    print("NetworkManager did not start in time", flush=True)
    return False


def wifi_on():
    """
    Ensure Wi-Fi radio is enabled.
    """
    result = subprocess.run(
        ["/usr/bin/nmcli", "radio", "wifi"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True
    )

    if result.stdout.strip().lower() == "disabled":
        print("Wi-Fi is off → enabling", flush=True)
        subprocess.run(["/usr/bin/nmcli", "radio", "wifi", "on"])
        time.sleep(2)
    else:
        print("Wi-Fi already enabled", flush=True)


def connected_to_any_wifi():
    """
    Check if any Wi-Fi interface is already connected.
    """
    result = subprocess.run(
        ["/usr/bin/nmcli", "-t", "-f", "TYPE,STATE", "device"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True
    )

    for line in result.stdout.splitlines():
        dev_type, state = line.split(":")
        if dev_type == "wifi" and state == "connected":
            return True

    return False


def connect_wifi(ssid, psk):
    """
    Create and activate a Wi-Fi connection.
    Supports hidden networks and safe connection names.
    """
    safe_name = sanitize_name(ssid)
    con_name = f"auto-{safe_name}"

    print(f"Connecting to SSID: {ssid}", flush=True)
    print(f"Using connection name: {con_name}", flush=True)

    # Remove existing connection with same name (idempotent)
    subprocess.run(
        ["/usr/bin/nmcli", "connection", "delete", con_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Create Wi-Fi connection (hidden SSID supported)
    result = subprocess.run(
        [
            "/usr/bin/nmcli", "connection", "add",
            "type", "wifi",
            "con-name", con_name,
            "ssid", ssid,
            "wifi.hidden", "yes",
            "wifi-sec.key-mgmt", "wpa-psk",
            "wifi-sec.psk", psk
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        print("Failed to create Wi-Fi connection", flush=True)
        print(result.stderr, flush=True)
        return False

    # Bring the connection up
    up = subprocess.run(
        ["/usr/bin/nmcli", "connection", "up", con_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if up.returncode == 0:
        print("Wi-Fi connected successfully", flush=True)
        return True
    else:
        print("Wi-Fi connection failed", flush=True)
        print(up.stderr, flush=True)
        return False


def main():
    """
    Main execution flow.
    """
    if connected_to_any_wifi():
        print("Already connected to a Wi-Fi network → doing nothing", flush=True)
        sys.exit(0)

    ssid, psk = read_wifi_file(WIFI_FILE)
    if not ssid or ssid.lower()=="wifi_network_name":
        print("No Wi-Fi credentials: SSID is empty or placeholder → exiting", flush=True)
        sys.exit(0)

    if not wait_for_networkmanager():
        sys.exit(1)

    wifi_on()

    if not connect_wifi(ssid, psk):
        sys.exit(1)


if __name__ == "__main__":
    main()

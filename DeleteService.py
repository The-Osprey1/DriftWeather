#!/usr/bin/env python3
"""
Safely delete a systemd service.
"""

import os
import sys
import subprocess

# Name of the service to delete
service_name = "G4Cast.service"

# Full path to the service file
service_file_path = f"/etc/systemd/system/{service_name}"

# Ensure script is run as root
if os.geteuid() != 0:
    print("ERROR: This script must be run as root")
    sys.exit(1)

try:
    # Stop the service if running
    print(f"Stopping service {service_name}...")
    subprocess.run(["systemctl", "stop", service_name], check=True)

    # Disable the service
    print(f"Disabling service {service_name}...")
    subprocess.run(["systemctl", "disable", service_name], check=True)

    # Remove the service file if it exists
    if os.path.exists(service_file_path):
        print(f"Removing service file {service_file_path}...")
        os.remove(service_file_path)
    else:
        print(f"Service file {service_file_path} does not exist!")

    # Reload systemd daemon to apply changes
    print("Reloading systemd daemon...")
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "reset-failed"], check=True)

    print(f"Service {service_name} has been deleted successfully.")

except subprocess.CalledProcessError as e:
    print(f"ERROR: Command failed: {e}")
    sys.exit(1)

except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)


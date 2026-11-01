#!/bin/bash
set -e
/usr/bin/python3 "$(dirname "$0")/ConnectWifi.py"
/usr/bin/python3 "$(dirname "$0")/G4Cast.py"
#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
Script for Waveshare 7.5" V2 e-Paper display.
Initializes the display, clears it, and puts it to sleep.
"""

import sys
import os
from pathlib import Path
import logging
import traceback

# Import the Waveshare e-Paper driver
from waveshare_epd import epd7in5_V2

# Configure logging to show DEBUG-level messages
logging.basicConfig(level=logging.DEBUG)

def main():
    """
    Main function to initialize, clear, and sleep the e-Paper display.
    Wrapped in a try-except block for proper error handling.
    """
    epd = None  # Initialize epd variable to ensure it's defined in case of early exception

    try:
        logging.info("epd7in5_V2 Demo starting...")

        # Initialize the display driver
        logging.info("Creating EPD instance")
        epd = epd7in5_V2.EPD()
        
        # Initialize the hardware and clear the display
        logging.info("Initializing and clearing the display")
        epd.init()
        epd.Clear()

        # Put the display into sleep mode to save power
        logging.info("Putting display to sleep...")
        epd.sleep()
    
    except IOError as e:
        # Catch any IO errors (e.g., SPI communication errors)
        logging.error("IOError occurred: %s", e)
        logging.debug(traceback.format_exc())
    
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        logging.info("KeyboardInterrupt received, exiting...")
        if epd:
            # Ensure the epdconfig cleanup function is called to release GPIO
            epd7in5_V2.epdconfig.module_exit(cleanup=True)
        sys.exit(0)
    
    except Exception as e:
        # Catch all other exceptions and log them
        logging.error("Unexpected error: %s", e)
        logging.debug(traceback.format_exc())
        if epd:
            epd7in5_V2.epdconfig.module_exit(cleanup=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

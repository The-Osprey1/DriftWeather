#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G4Cast E-Paper Hardware Abstraction
Controls Waveshare 7.5-inch V2 e-paper display with fast/full refresh and partial update flip transitions.
"""

import time
import logging
import threading
from typing import Optional
from PIL import Image

from .renderer import to_sharp_1bit

logger = logging.getLogger("G4Cast.EPaper")

try:
    from waveshare_epd import epd7in5_V2
    HAS_EPAPER = True
except Exception as e:
    epd7in5_V2 = None
    HAS_EPAPER = False
    logger.info("Waveshare e-paper hardware driver not detected (running in virtual mirror mode)")

class EPaperDisplay:
    _instance = None
    _lock = threading.RLock()

    def __init__(self):
        self.epd = None
        self.refresh_count = 0
        self.last_displayed_time = None
        self._init_hardware()

    def _init_hardware(self):
        if HAS_EPAPER and epd7in5_V2:
            try:
                self.epd = epd7in5_V2.EPD()
                logger.info("Waveshare 7.5 V2 display initialized successfully")
            except Exception as e:
                logger.error(f"EPD initialization error: {e}")
                self.epd = None

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def display_image(self, img: Image.Image, force_full: bool = False, rotation: int = 180):
        """Update e-paper display with new image."""
        with self._lock:
            rotated = img.rotate(rotation)
            sharp_1bit = to_sharp_1bit(rotated)

            if not self.epd:
                logger.debug("Virtual mode: image updated in buffer (cycle %d)", self.refresh_count + 1)
                self.refresh_count += 1
                return

            try:
                buf = self.epd.getbuffer(sharp_1bit)
                # Full refresh on first boot (count == 0), maintenance cycle, or explicit force_full
                if force_full or self.refresh_count == 0 or (self.refresh_count % 24 == 0):
                    logger.info("Performing full maintenance refresh to purge ghosting (cycle %d)...", self.refresh_count)
                    self.epd.init()
                else:
                    logger.info("Performing fast refresh (cycle %d)...", self.refresh_count)
                    self.epd.init_fast()

                self.epd.display(buf)
                self.refresh_count += 1
                self.epd.sleep()
                logger.info("Hardware display refresh complete (cycle %d)", self.refresh_count)
            except Exception as e:
                logger.error("Display update error: %s", e)

    def clean_display(self):
        """Perform a deep 3-cycle clean to completely erase residual e-ink ghosting."""
        with self._lock:
            logger.info("Initiating deep screen cleaning cycle...")
            if not self.epd:
                logger.info("Virtual mode: clean display completed")
                return

            try:
                self.epd.init()
                self.epd.Clear()
                time.sleep(1)
                self.epd.Clear()
                self.epd.sleep()
                logger.info("Deep screen cleaning cycle complete.")
            except Exception as e:
                logger.error("Error during clean display: %s", e)

    def update_clock_partial(self, img: Image.Image, local_dt, get_font_func, use_24h: bool = False, dark_mode: bool = False, rotation: int = 180, animate: bool = True):
        """Perform sub-second partial e-paper refresh for the minute clock."""
        from PIL import ImageDraw
        with self._lock:
            card_x0, card_y0 = 20, 154
            card_w, card_h = 270, 314
            card_x1, card_y1 = card_x0 + card_w, card_y0 + card_h
            card_cx = card_x0 + card_w // 2

            if use_24h:
                time_str = local_dt.strftime("%H:%M")
                ampm_str = ""
            else:
                time_str = local_dt.strftime("%I:%M").lstrip("0")
                ampm_str = local_dt.strftime("%p")

            if self.last_displayed_time == time_str:
                return

            draw = ImageDraw.Draw(img)
            f_clock = get_font_func("bold", 40)
            f_ampm = get_font_func("bold", 16)

            if hasattr(draw, "textbbox"):
                b1 = draw.textbbox((0, 0), time_str, font=f_clock)
                cw, ch = b1[2] - b1[0], b1[3] - b1[1]
                if ampm_str:
                    b2 = draw.textbbox((0, 0), ampm_str, font=f_ampm)
                    aw, ah = b2[2] - b2[0], b2[3] - b2[1]
                else:
                    aw, ah = 0, 0
            else:
                cw, ch = draw.textsize(time_str, font=f_clock)
                aw, ah = draw.textsize(ampm_str, font=f_ampm) if ampm_str else (0, 0)

            clock_block_w = cw + (8 + aw if ampm_str else 0)
            clock_start_x = card_cx - clock_block_w // 2

            COLOR_BG = 0 if dark_mode else 255
            COLOR_FG = 255 if dark_mode else 0

            # FRAME 1 (Mechanical Split-Flap Transition)
            should_flip = animate and (self.epd is not None) and (self.last_displayed_time is not None)
            if should_flip:
                draw.rectangle([card_x0 + 4, card_y0 + 258, card_x1 - 4, card_y1 - 4], fill=COLOR_BG)
                draw.text((clock_start_x, card_y0 + 261), time_str, font=f_clock, fill=COLOR_FG)
                if ampm_str:
                    draw.text((clock_start_x + cw + 8, card_y0 + 274), ampm_str, font=f_ampm, fill=COLOR_FG)

                seam_y = card_y0 + 283
                draw.line([(clock_start_x - 4, seam_y), (clock_start_x + clock_block_w + 4, seam_y)], fill=COLOR_BG, width=2)
                draw.line([(clock_start_x - 4, seam_y + 1), (clock_start_x + clock_block_w + 4, seam_y + 1)], fill=COLOR_FG, width=1)

                try:
                    self.epd.init_part()
                    rotated = img.rotate(rotation)
                    sharp = to_sharp_1bit(rotated)
                    self.epd.display_Partial(self.epd.getbuffer(sharp), 0, 0, self.epd.width, self.epd.height)
                    time.sleep(0.12)
                except Exception as e:
                    logger.debug("Partial flip frame 1 note: %s", e)

            # FRAME 2 (Final settled digits)
            draw.rectangle([card_x0 + 4, card_y0 + 258, card_x1 - 4, card_y1 - 4], fill=COLOR_BG)
            draw.text((clock_start_x, card_y0 + 263), time_str, font=f_clock, fill=COLOR_FG)
            if ampm_str:
                draw.text((clock_start_x + cw + 8, card_y0 + 274), ampm_str, font=f_ampm, fill=COLOR_FG)

            self.last_displayed_time = time_str

            if self.epd:
                try:
                    self.epd.init_part()
                    rotated = img.rotate(rotation)
                    sharp = to_sharp_1bit(rotated)
                    self.epd.display_Partial(self.epd.getbuffer(sharp), 0, 0, self.epd.width, self.epd.height)
                    self.epd.sleep()
                except Exception as e:
                    logger.error("Partial refresh error: %s", e)

def get_display():
    return EPaperDisplay.get_instance()

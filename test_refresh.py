import time
import logging
from PIL import Image
from waveshare_epd import epd7in5_V2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    logging.info("Testing fast refresh on Waveshare 7.5 V2...")
    epd = epd7in5_V2.EPD()

    t0 = time.time()
    epd.init_fast()
    logging.info(f"init_fast completed in {time.time() - t0:.2f}s")

    img = Image.open("/home/user/G4Cast/preview_clean.png").convert("L")
    buf = epd.getbuffer(img.rotate(180))

    t0 = time.time()
    epd.display(buf)
    logging.info(f"display (fast waveform) completed in {time.time() - t0:.2f}s")

    epd.sleep()
    logging.info("Fast refresh test completed successfully!")

if __name__ == "__main__":
    main()

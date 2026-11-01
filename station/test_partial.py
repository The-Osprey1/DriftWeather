import time
import logging
from PIL import Image
from waveshare_epd import epd7in5_V2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    logging.info("Testing partial refresh timing...")
    epd = epd7in5_V2.EPD()

    t0 = time.time()
    epd.init_part()
    logging.info(f"init_part took: {time.time() - t0:.2f}s")

    img = Image.open("/home/user/G4Cast/preview_clean.png").convert("L")
    buf = epd.getbuffer(img.rotate(180))

    t0 = time.time()
    epd.display_Partial(buf, 0, 0, epd.width, epd.height)
    logging.info(f"display_Partial took: {time.time() - t0:.2f}s")

    epd.sleep()
    logging.info("Done.")

if __name__ == "__main__":
    main()

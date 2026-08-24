##########
# Description: Capture the FULL screen so you can read real pixel coordinates,
#              then optionally crop + OCR a given zone from that same image.
# Usage:
#   python utils/pos_finder/test_capture.py             -> full screen capture
#   python utils/pos_finder/test_capture.py x1 y1 x2 y2 -> full capture + crop/OCR
##########

import re
import sys
import time

import pyautogui
import pytesseract
from PIL import Image

# Same tesseract path as in the main bot
pytesseract.pytesseract.tesseract_cmd = r'D:\tesseract\tesseract.exe'


def parse_price(text: str) -> int:
    """Extract the first number found in the OCR text (handles spaces as separators)."""
    matches = re.findall(r'[\d\s]+', text)
    for match in matches:
        digits = ''.join(filter(str.isdigit, match))
        if digits:
            return int(digits)
    return 1


def main():
    print(f"Screen resolution : {pyautogui.size()}")
    print("Capturing in 6 seconds... switch to the Dofus window now!")
    time.sleep(6)

    # Full-screen capture with pyautogui (same backend as the bot's clicks).
    full = pyautogui.screenshot()
    full.save("capture_full.png")
    print(f"Full screen saved to: capture_full.png  (size={full.size})")

    if len(sys.argv) == 5:
        x1, y1, x2, y2 = (int(v) for v in sys.argv[1:5])
        # Crop from the full screenshot -> guarantees the SAME coordinate system
        crop = full.crop((x1, y1, x2, y2))
        crop.save("capture_test.png")
        text = pytesseract.image_to_string(crop)
        print("-" * 40)
        print(f"bbox              : {(x1, y1, x2, y2)}")
        print(f"Crop saved to     : capture_test.png (size={crop.size})")
        print(f"Raw OCR text      : {text!r}")
        print(f"Parsed price      : {parse_price(text)} Kamas")
        print("-" * 40)
    else:
        print("Open capture_full.png, hover pixels to read real coordinates,")
        print("then run: python utils/pos_finder/test_capture.py x1 y1 x2 y2")


if __name__ == "__main__":
    main()


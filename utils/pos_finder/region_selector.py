##########
# Description: Visual region selector. Opens a screenshot, let you DRAW a
#              rectangle with the mouse, and prints the bbox coordinates + OCR.
# Usage: python utils/pos_finder/region_selector.py [image.png]
#        (defaults to capture_full.png)
##########

import sys

import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r'D:\tesseract\tesseract.exe'

image_path = sys.argv[1] if len(sys.argv) > 1 else "capture_full.png"
img = Image.open(image_path)


def onselect(eclick, erelease):
    x1, y1 = int(eclick.xdata), int(eclick.ydata)
    x2, y2 = int(erelease.xdata), int(erelease.ydata)
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    crop = img.crop((x1, y1, x2, y2))
    text = pytesseract.image_to_string(crop).strip()
    print("=" * 50)
    print(f"bbox = ({x1}, {y1}, {x2}, {y2})")
    print(f"OCR  = {text!r}")
    print("=" * 50)


fig, ax = plt.subplots(figsize=(14, 8))
ax.imshow(img)
ax.set_title("Draw a rectangle around the price. Coordinates print in the terminal.")

selector = RectangleSelector(
    ax, onselect, useblit=True, button=[1],
    minspanx=5, minspany=5, spancoords="pixels", interactive=True,
)

plt.show()

# Finds the liquid y-coordinate with plain OpenCV (no model), assuming the image is already
# cropped so the top of the image is the top of the beaker and the bottom is its bottom.
# Idea: the liquid surface is a horizontal edge. A vertical Sobel (responds to horizontal edges)
# averaged across the middle strip gives one number per row; the strongest peak is the liquid line.
# fill % = (bottom - liquid) / (bottom - top) * 100 - this is straight from the read me.
#
# No peak means no liquid surface is visible, which is either empty OR full. Edges can't tell
# those apart, so the strip is compared to a photo of the same empty beaker: same as the
# empty photo -> empty, different -> full. Without an empty photo the result is "unknown". -
# dont want any guessing ^^^
#
# Usage: python ycoordinate.py <image> [empty_image]
#        python ycoordinate.py                 (webcam; press e with the beaker empty to save the reference, q to quit)

import sys
import cv2
import numpy as np

STRIP = 0.4          # fraction of the width (centered) used, like the labeling guideline
PEAK_MIN = 8.0       # minimum edge strength (0-255 gray levels per pixel) to count as a liquid line; tune on real photos
BORDER = 0.05        # ignore this fraction at the top and bottom, where the rim and base edges are
EMPTY_DIFF = 12.0    # mean gray difference from the empty reference above which the beaker counts as full; tune on real photos

# middle strip of the image as smoothed grayscale
def middle_strip (image) :
    gray = cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    w = gray.shape[1]
    margin = int(w * (1 - STRIP) / 2)
    return gray[:, margin:w - margin]

# Returns (liquid_y, fill %). liquid_y is None when no liquid line is found; fill is then
# 0 (matches the empty reference), 100 (differs from it), or None (no reference given).
def find_liquid (image, emptyImage = None) :
    strip = middle_strip(image)
    h = strip.shape[0]

    profile = np.abs(cv2.Sobel(strip, cv2.CV_64F, 0, 1, ksize = 3)).mean(axis = 1)
    profile = np.convolve(profile, np.ones(5) / 5, mode = "same")

    lo, hi = int(h * BORDER), int(h * (1 - BORDER))
    y = lo + int(profile[lo:hi].argmax())

    if profile[y] >= PEAK_MIN :
        return y, (h - 1 - y) / (h - 1) * 100

    if emptyImage is None :
        return None, None
    ref = cv2.resize(middle_strip(emptyImage), (strip.shape[1], h))
    diff = np.abs(strip.astype(np.float32) - ref.astype(np.float32)).mean()
    return None, 100.0 if diff > EMPTY_DIFF else 0.0

def draw (image, y, fill) :
    out = image.copy()
    if y is not None :
        cv2.line(out, (0, y), (out.shape[1], y), (0, 255, 0), 2)
    text = "fill unknown" if fill is None else f"fill {fill:.0f}%"
    cv2.putText(out, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    return out

def main () :
    if len(sys.argv) >= 2 :
        image = cv2.imread(sys.argv[1])
        empty = cv2.imread(sys.argv[2]) if len(sys.argv) > 2 else None
        if image is None :
            raise ValueError("Could not open or find the image")
        y, fill = find_liquid(image, empty)
        print(f"liquid y: {y}  fill: {fill}")
        cv2.imwrite("ycoordinate_out.png", draw(image, y, fill))
        return

    cap = cv2.VideoCapture(0)
    empty = None
    while True :
        ok, frame = cap.read()
        if not ok :
            break
        y, fill = find_liquid(frame, empty)
        cv2.imshow("ycoordinate (e = empty reference, q = quit)", draw(frame, y, fill))
        key = cv2.waitKey(1) & 0xFF
        if key == ord("e") :
            empty = frame.copy()
        elif key == ord("q") :
            break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__" :
    main()

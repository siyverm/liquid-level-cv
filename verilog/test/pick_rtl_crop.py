# Pick a crop box on an image by dragging, and print the bounds for the RTL tester.
# Optionally make a 128x128 version of the image (with the box converted to it) and
# save it to testImges/resized_128/.
#
# Usage (from verilog/test, with cocotb-env or the repo .venv active):
#   python pick_rtl_crop.py                 # asks for the image path
#   python pick_rtl_crop.py path/to/img.jpg
#
# Drag a box, then press ENTER or SPACE to accept (C cancels).
# Coordinates are in the pixels of the image you pick.

import sys
from pathlib import Path

import cv2

DISPLAY_SIZE = 768   # small images are enlarged to about this size so the box is easy to draw
RTL_SIZE = 128       # size of the saved square image
OUT_DIR = Path(__file__).resolve().parent / "testImges" / "resized_128"


def scaled_for_display(image):
    scale = DISPLAY_SIZE / max(image.shape[:2])
    interp = cv2.INTER_NEAREST if scale > 1 else cv2.INTER_AREA
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=interp), scale


def pick_box(image):
    imgH, imgW = image.shape[:2]
    shown, scale = scaled_for_display(image)

    title = "Drag a box, ENTER to accept, C to cancel"
    x, y, w, h = cv2.selectROI(title, shown, showCrosshair=True)
    cv2.destroyAllWindows()
    cv2.waitKey(1)   # macOS needs this for the window to actually close

    if w == 0 or h == 0:
        raise SystemExit("No box selected.")

    # back to real image pixels, clamped inside the image
    left = max(0, round(x / scale))
    top = max(0, round(y / scale))
    right = min(imgW, round((x + w) / scale))
    bottom = min(imgH, round((y + h) / scale))
    if right <= left or bottom <= top:
        raise SystemExit("Box is too small after converting to image pixels.")
    return (left, top, right, bottom)


def show_preview(image, box, title):
    left, top, right, bottom = box
    preview, scale = scaled_for_display(image)
    cv2.rectangle(preview, (int(left * scale), int(top * scale)),
                  (int(right * scale), int(bottom * scale)), (0, 0, 255), 2)
    cv2.imshow(title + " (press any key to close)", preview)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    cv2.waitKey(1)


def print_bounds(image, box, heading):
    left, top, right, bottom = box
    imgH, imgW = image.shape[:2]
    print()
    print(f"=== {heading} ===")
    print(f"Image size: {imgW} x {imgH}")
    print(f"Crop size:  {right - left} x {bottom - top}")
    print()
    print("Python (crop_image_fixed, right/bottom exclusive):")
    print(f"    CROP_BOX = ({left}, {top}, {right}, {bottom})")
    print()
    print("RTL parameters (inclusive):")
    print(f"    TOP_LEFT_X={left} TOP_LEFT_Y={top} BOTTOM_RIGHT_X={right - 1} BOTTOM_RIGHT_Y={bottom - 1}")
    print()
    print("Makefile EXTRA_ARGS:")
    print(f"    -GWIDTH={imgW} -GHEIGHT={imgH} -GTOP_LEFT_X={left} -GTOP_LEFT_Y={top} "
          f"-GBOTTOM_RIGHT_X={right - 1} -GBOTTOM_RIGHT_Y={bottom - 1}")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# Makes the image square without losing the box, then shrinks it to RTL_SIZE.
# Normally trims the long side with the square positioned around the box (no stretching,
# no padding). Only if the box is longer than the image's short side does it pad instead,
# copying the edge pixels so the padding doesn't create a fake edge.
# Returns (square image, box in the square image's pixels, description of what was done).
def make_square(image, box):
    imgH, imgW = image.shape[:2]
    left, top, right, bottom = box

    side = min(imgH, imgW)
    if (right - left) <= side and (bottom - top) <= side:
        # square window centered on the box, moved as needed to stay inside the image
        # and to contain the whole box
        cx, cy = (left + right) / 2, (top + bottom) / 2
        x0 = clamp(round(cx - side / 2), max(0, right - side), min(left, imgW - side))
        y0 = clamp(round(cy - side / 2), max(0, bottom - side), min(top, imgH - side))
        square = image[y0:y0 + side, x0:x0 + side]
        how = f"trimmed to {side}x{side} at x={x0}..{x0 + side - 1}, y={y0}..{y0 + side - 1}"
    else:
        side = max(imgH, imgW)
        padTop = (side - imgH) // 2
        padLeft = (side - imgW) // 2
        square = cv2.copyMakeBorder(image, padTop, side - imgH - padTop, padLeft, side - imgW - padLeft,
                                    cv2.BORDER_REPLICATE)
        x0, y0 = -padLeft, -padTop
        how = f"box too large to trim around, padded to {side}x{side} (edge pixels repeated)"

    scale = RTL_SIZE / side
    small = cv2.resize(square, (RTL_SIZE, RTL_SIZE),
                       interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)

    newLeft = clamp(round((left - x0) * scale), 0, RTL_SIZE - 1)
    newTop = clamp(round((top - y0) * scale), 0, RTL_SIZE - 1)
    newRight = clamp(round((right - x0) * scale), newLeft + 1, RTL_SIZE)
    newBottom = clamp(round((bottom - y0) * scale), newTop + 1, RTL_SIZE)
    return small, (newLeft, newTop, newRight, newBottom), how


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else input("Image path: ").strip().strip("'\"")
    image = cv2.imread(path)
    if image is None:
        raise SystemExit(f"Could not open image: {path}")

    box = pick_box(image)
    print_bounds(image, box, "Bounds on the image you picked")
    show_preview(image, box, "Chosen crop")

    if image.shape[:2] == (RTL_SIZE, RTL_SIZE):
        print(f"\nImage is already {RTL_SIZE}x{RTL_SIZE}, nothing to resize.")
        return

    answer = input(f"\nResize to {RTL_SIZE}x{RTL_SIZE} and save to {OUT_DIR.name}/? (y/n): ")
    if answer.strip().lower() != "y":
        return

    small, smallBox, how = make_square(image, box)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outPath = OUT_DIR / Path(path).name
    existed = outPath.exists()
    if not cv2.imwrite(str(outPath), small):
        raise SystemExit(f"Could not save {outPath}")

    print(f"\nSquare: {how}")
    print(f"{'Overwrote' if existed else 'Saved'} {outPath}")
    print_bounds(small, smallBox, f"Bounds on the saved {RTL_SIZE}x{RTL_SIZE} image (use these)")
    show_preview(small, smallBox, f"Saved {RTL_SIZE}x{RTL_SIZE} image")


if __name__ == "__main__":
    main()

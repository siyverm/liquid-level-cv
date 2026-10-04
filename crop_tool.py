# Interactive tool for choosing a fixed crop box for a controlled session.
# Run once per setup: draw a box on a reference photo, check it on every photo
# in that session, then save it to crop_boxes.csv for preprocessing.py to use.
# Needs a screen to open a window, so it's kept out of preprocessing.py.

import cv2
import os
import pandas as pd
from preprocessing import crop_image_fixed, get_session_id, load_crop_boxes, CROP_BOXES_PATH

IMAGE_DIRECTORY = "images"
PREVIEW_DIRECTORY = "cropPreview"

# Opens an image so you can drag a box around the container, then returns that box
# as fractions (left, top, right, bottom), ready for crop_image_fixed(..., fractional = True).
def pick_crop_box (imagePath, maxDisplay = 900) :
    image = cv2.imread(imagePath)
    if image is None :
        raise ValueError("Could not open or find the image")
    imgH, imgW = image.shape[:2]

    # shrink large photos so they fit on screen
    display = min(1.0, maxDisplay / max(imgH, imgW))
    shown = cv2.resize(image, None, fx = display, fy = display)

    x, y, w, h = cv2.selectROI("Drag a box around the container, then press ENTER", shown, showCrosshair = True)
    cv2.destroyAllWindows()
    cv2.waitKey(1)   # macOS needs this for the window to actually close

    if w == 0 or h == 0 :
        raise ValueError("No box selected")

    # undo the display scaling, then convert to fractions of the full image
    box = (x / display / imgW, y / display / imgH,
           (x + w) / display / imgW, (y + h) / display / imgH)
    return tuple(round(v, 4) for v in box)

# Saves each image cropped with the given box so you can check the box fits all of them.
def preview_crop_box (imagePaths, box, outDir) :
    os.makedirs(outDir, exist_ok = True)
    for path in imagePaths :
        cropped, _ = crop_image_fixed(cv2.imread(path), box, fractional = True)
        cv2.imwrite(os.path.join(outDir, os.path.basename(path)), cropped)

# Adds or replaces a session's box in crop_boxes.csv.
def save_crop_box (sessionId, box, path = CROP_BOXES_PATH) :
    boxes = load_crop_boxes(path)
    boxes[sessionId] = box
    rows = [[sid, *b] for sid, b in boxes.items()]
    pd.DataFrame(rows, columns = ["session_id", "left", "top", "right", "bottom"]).to_csv(path, index = False)

def main () :
    path = input("Path of a reference image from the session: ")
    sessionId = get_session_id(path)

    # a box for the blank session would apply to every photo with no session filled in
    if sessionId == "" :
        print("This image has no session ID, so a crop box can't be saved for it.")
        return

    box = pick_crop_box(path)
    print(f"Crop box for session '{sessionId}': {box}")

    sessionImages = [os.path.join(IMAGE_DIRECTORY, f) for f in sorted(os.listdir(IMAGE_DIRECTORY))
                     if f.lower().endswith((".jpg", ".jpeg", ".png")) and get_session_id(f) == sessionId]
    outDir = os.path.join(PREVIEW_DIRECTORY, sessionId)
    preview_crop_box(sessionImages, box, outDir)
    print(f"Saved {len(sessionImages)} cropped previews to {outDir}/ - check the container fits in all of them.")

    if input(f"Save this box to {CROP_BOXES_PATH}? (y/n): ").strip().lower() == "y" :
        save_crop_box(sessionId, box)
        print("Saved.")
    else :
        print("Not saved.")

if __name__ == "__main__" :
    main()

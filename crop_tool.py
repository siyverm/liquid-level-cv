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
SLIT_WIDTH = 30   # pixels, in the full-size image

# Narrows a fractional box to a slit SLIT_WIDTH pixels wide, starting at the box's left side.
def to_slit (box, imgW) :
    left, top, right, bottom = box
    return (left, top, round(min(1.0, left + SLIT_WIDTH / imgW), 4), bottom)

# Converts a fractional slit box to pixel edges (left, left + SLIT_WIDTH, bottom, top).
def slit_edges (box, imgW, imgH) :
    left, top, right, bottom = box
    return (int(round(left * imgW)), int(round(right * imgW)), int(round(bottom * imgH)), int(round(top * imgH)))

# Opens an image so you can drag a box around the container, then returns that box
# as fractions (left, top, right, bottom), ready for crop_image_fixed(..., fractional = True).
# With slit = True, the box is narrowed to a SLIT_WIDTH-pixel slit from its left side.
def pick_crop_box (imagePath, maxDisplay = 900, slit = False) :
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
    box = tuple(round(v, 4) for v in box)
    return to_slit(box, imgW) if slit else box

# Same as pick_crop_box, but on live video. Drag a box at any time, on the moving feed or a
# frozen frame, and a second window shows the cropped feed so you can check it as things move.
# Keys: SPACE freezes/unfreezes, R clears the box, ENTER accepts, Q or ESC quits.
# Returns (box, frame): the box as fractions and the full-size frame it was accepted on.
def pick_crop_box_live (source = 0, maxDisplay = 900, slit = False) :
    cap = cv2.VideoCapture(source)
    if not cap.isOpened() :
        raise ValueError(f"Could not open video source {source}")

    window = "Drag a box around the container - SPACE freeze, R reset, ENTER accept, Q quit"
    cropWindow = "Cropped"
    drag = {"start": None, "end": None, "dragging": False}

    # mouse positions are in display pixels, which is fine because the box is stored as fractions
    def on_mouse (event, x, y, flags, param) :
        if event == cv2.EVENT_LBUTTONDOWN :
            drag.update(start = (x, y), end = (x, y), dragging = True)
        elif event == cv2.EVENT_MOUSEMOVE and drag["dragging"] :
            drag["end"] = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and drag["dragging"] :
            drag.update(end = (x, y), dragging = False)

    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_mouse)

    frozen = None
    frame = None
    box = None
    cropShown = False
    try :
        while True :
            if frozen is None :
                ok, frame = cap.read()
                if not ok :
                    raise ValueError("Lost the video feed")
            else :
                frame = frozen
            imgH, imgW = frame.shape[:2]

            # shrink large frames so they fit on screen
            display = min(1.0, maxDisplay / max(imgH, imgW))
            shown = cv2.resize(frame, None, fx = display, fy = display)
            shownH, shownW = shown.shape[:2]

            # turn the drag into a fractional box, ignoring clicks that didn't really drag
            box = None
            if drag["start"] is not None :
                (x1, y1), (x2, y2) = drag["start"], drag["end"]
                x1, x2 = sorted((min(max(x1, 0), shownW), min(max(x2, 0), shownW)))
                y1, y2 = sorted((min(max(y1, 0), shownH), min(max(y2, 0), shownH)))
                if x2 - x1 > 2 and y2 - y1 > 2 :
                    box = tuple(round(v, 4) for v in (x1 / shownW, y1 / shownH, x2 / shownW, y2 / shownH))
                    if slit :
                        box = to_slit(box, imgW)
                    cv2.rectangle(shown, (int(box[0] * shownW), int(box[1] * shownH)),
                                  (int(box[2] * shownW), int(box[3] * shownH)), (0, 255, 0), 2)

            if frozen is not None :
                cv2.putText(shown, "FROZEN", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.imshow(window, shown)

            if box is not None :
                cropped, _ = crop_image_fixed(frame, box, fractional = True)
                cv2.imshow(cropWindow, cropped)
                cropShown = True
            elif cropShown :
                cv2.destroyWindow(cropWindow)
                cropShown = False

            key = cv2.waitKey(1) & 0xFF
            if key == ord(" ") :
                frozen = None if frozen is not None else frame.copy()
            elif key in (ord("r"), ord("R")) :
                drag.update(start = None, end = None, dragging = False)
            elif key in (13, 10) and box is not None :   # ENTER
                return box, frame
            elif key in (ord("q"), ord("Q"), 27) :
                raise ValueError("No box selected")
    finally :
        cap.release()
        cv2.destroyAllWindows()
        cv2.waitKey(1)   # macOS needs this for the window to actually close

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

# Picks a box from live video. Nothing is written to crop_boxes.csv; the box is just printed.
def main_live (slit = False) :
    source = input("Webcam index (blank for 0): ").strip()
    box, frame = pick_crop_box_live(int(source) if source else 0, slit = slit)
    print(f"Crop box: {box}")
    if slit :
        print_slit(box, frame)

    outDir = os.path.join(PREVIEW_DIRECTORY, "live")
    os.makedirs(outDir, exist_ok = True)
    cropped, _ = crop_image_fixed(frame, box, fractional = True)
    cv2.imwrite(os.path.join(outDir, "frame.png"), cropped)
    print(f"Saved the cropped video frame to {outDir}/frame.png")

    # optional: check the box against photos already taken for a session
    sessionId = input("Session ID to preview photos from (blank to skip): ").strip()
    if sessionId :
        sessionImages = [os.path.join(IMAGE_DIRECTORY, f) for f in sorted(os.listdir(IMAGE_DIRECTORY))
                         if f.lower().endswith((".jpg", ".jpeg", ".png")) and get_session_id(f) == sessionId]
        preview_crop_box(sessionImages, box, outDir)
        print(f"Saved {len(sessionImages)} cropped previews to {outDir}/ - check the container fits in all of them.")

def print_slit (box, image) :
    imgH, imgW = image.shape[:2]
    left, right, bottom, top = slit_edges(box, imgW, imgH)
    print(f"Slit in pixels: left = {left}, left + {SLIT_WIDTH} = {right}, bottom = {bottom}, top = {top}")

def main () :
    slit = input("Crop the (w)hole beaker or a (s)lit? ").strip().lower() == "s"
    if input("Pick the box from a (p)hoto or live (v)ideo? ").strip().lower() == "v" :
        main_live(slit)
        return

    path = input("Path of a reference image from the session: ")
    sessionId = get_session_id(path)

    # a box for the blank session would apply to every photo with no session filled in
    if sessionId == "" :
        print("This image has no session ID, so a crop box can't be saved for it.")
        return

    box = pick_crop_box(path, slit = slit)
    print(f"Crop box for session '{sessionId}': {box}")
    if slit :
        print_slit(box, cv2.imread(path))

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

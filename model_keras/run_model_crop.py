import os
import numpy as np
import pandas as pd
import cv2
import tensorflow as tf
from keras import layers, Model, callbacks
import sys
import keras
from making_model import make_model, predict

# Adds the parent directory (liquid-level-cv) to Python's module search path
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from crop_tool import pick_crop_box_live
from preprocessing import crop_image_fixed
from fill_percentage import predict_volume

#
# Code from this file is AI gen, it is purely used for testing. 
#

# Draws what the model sees: the image with a line at the strongest edge of each kind,
# next to a panel plotting the profile row by row.
# Green = dark above / light below (channel 0), red = light above / dark below (channel 1).
# Small images are scaled up to at least minHeight pixels tall so the lines are easy to see.
def draw_profile (img, profile, panelWidth = 150, minHeight = 400) :
    h = img.shape[0]
    scale = max(1.0, minHeight / h)
    shown = cv2.resize(img, None, fx = scale, fy = scale, interpolation = cv2.INTER_NEAREST)
    shownH, shownW = shown.shape[:2]
    panel = np.zeros((shownH, panelWidth, 3), dtype = np.uint8)

    # the "valid" convolution drops the top and bottom rows, so profile row i is image row i + 1
    rows = np.arange(profile.shape[0]) + 1
    centers = ((rows + 0.5) * scale).astype(np.int32)
    peak = profile.max()
    colors = [(0, 255, 0), (0, 0, 255)]   # BGR

    for c, color in enumerate(colors) :
        # both channels share one scale so their strengths can be compared
        values = profile[:, c] / peak if peak > 0 else np.zeros(len(rows))
        points = np.stack([(values * (panelWidth - 1)).astype(np.int32), centers], axis = 1)
        cv2.polylines(panel, [points], False, color, 1)

        if peak > 0 :
            y = int(rows[np.argmax(profile[:, c])])
            yShown = int((y + 0.5) * scale)
            cv2.line(shown, (0, yShown), (shownW - 1, yShown), color, 2)
            cv2.line(panel, (0, yShown), (panelWidth - 1, yShown), color, 1)
            cv2.putText(panel, f"y = {y}", (5, 20 + 20 * c), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    return np.hstack([shown, panel])

# Lets you drag a crop box around the container on live video (SPACE freeze, R reset,
# ENTER accept, Q quit), then builds the model at that crop's size and runs it on the
# cropped feed. Press Q in the "Cropped" window to stop.
def run_with_live_crop (source = 0, slit = False) :

    box, frame = pick_crop_box_live(source, slit = slit)
    cropped, _ = crop_image_fixed(frame, box, fractional = True)
    model = make_model(cropped.shape[1], cropped.shape[0])

    # the picker releases the camera when it closes, so open it again
    cap = cv2.VideoCapture(source)
    if not cap.isOpened() :
        raise ValueError(f"Could not open video source {source}")

    try :
        while True :
            ok, frame = cap.read()
            if not ok :
                break

            cropped, _ = crop_image_fixed(frame, box, fractional = True)
            profile = predict(model, cropped)

            predict_volume(profile)    

            cv2.imshow("Cropped", draw_profile(cropped, profile))
            if (cv2.waitKey(1) & 0xFF) in (ord("q"), ord("Q"), 27) :
                break
    finally :
        cap.release()
        cv2.destroyAllWindows()
        cv2.waitKey(1)   # macOS needs this for the window to actually close

def main () :
    if input("Pick a crop box first? (y/n): ").strip().lower() == "y" :
        slit = input("Crop the (w)hole beaker or a (s)lit? ").strip().lower() == "s"
        run_with_live_crop(slit = slit)
        return

    cap = cv2.VideoCapture(0)
    ok, frame = cap.read()
    model = make_model(frame.shape[1], frame.shape[0])

    while True :
        ok, frame = cap.read()
        if not ok :
            break
        
        fill = predict(model, frame)
        cv2.imshow("ycoordinate (e = empty reference, q = quit)", draw_profile(frame, fill))
        key = cv2.waitKey(1) & 0xFF
        if key == ord("e") :
            empty = frame.copy()
        elif key == ord("q") :
            break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__" :
    main()
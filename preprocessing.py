import cv2
import numpy as np
import time
import os
from datetime import datetime
import pandas as pd

# how far (in pixels of the 128x128 image) a label may sit outside the crop
# before it's treated as an error instead of a labeling slip
LABEL_TOLERANCE = 3

# known crop boxes for controlled sessions, written by crop_tool.py
CROP_BOXES_PATH = "crop_boxes.csv"

# Error for edge detection in cropping
class DetectionError(Exception) :
    pass

# Using canny, crops the image passed in to its edges. 
def crop_image_edge_detect (image) :
    # creates grey copy of image 
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit = 4.0, tileGridSize = (8,8))
    gray = clahe.apply(gray)

    # reduce noise
    blur = cv2.GaussianBlur(gray, (5,5), 0)

    # detect edges, uses brightness of image to deteremine adequate thresholds. 
    # Only works against light backgrounds for the time being.
    otsuVal, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    lower = int(max(0, 0.5 * otsuVal))
    upper = int(otsuVal)
    # print("lower: " + str(lower) + " | upper: " + str(upper))

    edges = cv2.Canny(blur, lower , upper)

    # removed any horizontal lines in the picture.
    lineMask = np.zeros_like(edges)
    linesP = cv2.HoughLinesP(
        edges,
        rho = 1,
        theta = np.pi / 180,
        threshold = 50,
        minLineLength = int(0.20 * image.shape[1]),
        maxLineGap = 20
    )
    if linesP is not None :
        for line in linesP:
            x1, y1, x2, y2 = [int(v) for v in np.array(line).flatten()[:4]]
            angle = np.degrees(np.arctan2(float(abs(y2 - y1)), float(abs(x2 - x1))))
            if angle < 10:
                cv2.line(lineMask, (x1,y1), (x2, y2), 255, thickness = 5)
    edges = cv2.subtract(edges, lineMask)

    # closes edges that dont connect
    kernelSize = max(3, int(0.01*min(image.shape[:2])))
    kernelCLOSE = cv2.getStructuringElement(cv2.MORPH_RECT, (kernelSize, kernelSize))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernelCLOSE)

    # Finds edges(contours) detected by Canny
    contours, _ =  cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # finds largest contour detected. 
    if not contours :
        raise DetectionError("No Contours Found.")
    
    # create a list of "good contours" that are large enough to be considered in the crop.
    goodContours = []
    for contour in contours :
        area = cv2.contourArea(contour)
        if area <= (0.0005 * image.shape[0] * image.shape[1]) :
            continue
        cx, cy, cw, ch = cv2.boundingRect(contour)
        aspect = cw / float(ch)
        # skip long thin horizontal fragments (floor line)
        if aspect > 8.0 and ch < 0.04 * image.shape[0] :
            continue
        goodContours.append(contour)

    if not goodContours :
        raise DetectionError("No Good Contours Found")

    # After all good contours are found, a box containing all of them is drawn and given in coordinates and size
    x, y, w, h = cv2.boundingRect(np.vstack(goodContours))

    # Sometimes the edge at the very bottom of the beaker gets thrown out. 
    # So we get the very bottom edge found, assuming that it is the edge. 
    beakerRegion = edges[:, x:x+w]
    ys, xs = np.nonzero(beakerRegion)
    if len(ys) > 0:
        lowestRimY = ys.max()
        newBottom = min(max(y + h, lowestRimY), image.shape[0])
        h = newBottom - y

    # crops image
    cropped = image[y:y+h, x:x+w]

    return cropped, (x, y, w, h)

# Crops the image to a known box instead of detecting it.
# Use in controlled setups where the camera and container don't move.
# box is (left, top, right, bottom), either in pixels or as fractions (0-1) of the image size.
def crop_image_fixed (image, box, fractional = False) :
    imgH, imgW = image.shape[:2]
    left, top, right, bottom = box

    # fractions let the same box work for photos of different resolutions
    if fractional :
        left, right = left * imgW, right * imgW
        top, bottom = top * imgH, bottom * imgH

    # round to whole pixels and keep the box inside the image
    x1 = max(0, int(round(left)))
    y1 = max(0, int(round(top)))
    x2 = min(imgW, int(round(right)))
    y2 = min(imgH, int(round(bottom)))

    if x2 <= x1 or y2 <= y1 :
        raise DetectionError(f"Crop box {box} is empty or outside the {imgW}x{imgH} image")

    cropped = image[y1:y2, x1:x2]
    return cropped, (x1, y1, x2 - x1, y2 - y1)

# resizes image to make constant in training and prediciton
def resize (image) :
    # Shrink by the greatest amount needed to get 128 on that side
    heightConstraint = 128 / image.shape[0]
    widthConstraint = 128 / image.shape[1]

    scaleFactor = min(widthConstraint, heightConstraint)
    resizedImage = cv2.resize(image, None, fx = scaleFactor, fy = scaleFactor)

    #Padding sides that scaled too much, ensures that proportions and size is constant. 
    heightPadding = 128 - min(128, resizedImage.shape[0])
    widthPadding  = 128 - min(128, resizedImage.shape[1])

    topPad = heightPadding // 2
    bottomPad = heightPadding - topPad
    leftPad = widthPadding // 2
    rightPad = widthPadding - leftPad

    bordered = cv2.copyMakeBorder(resizedImage, topPad, bottomPad, 
                                  leftPad, rightPad, cv2.BORDER_CONSTANT, value = (0, 0, 0))

    return bordered, scaleFactor, topPad

# preprocessing function. Runs above functions and normalizes colors 0 - 1 instead of 1 - 256.
# Uses the given crop box if there is one, otherwise finds the container with edge detection.
def preprocess (imagePath, cropBox = None, fractional = False) :
    image = cv2.imread(imagePath)

    if image is None :
        raise ValueError("Could not open or find the image")

    if cropBox is None :
        cropped, cropBox = crop_image_edge_detect(image)
    else :
        cropped, cropBox = crop_image_fixed(image, cropBox, fractional)
    resized, scaleFactor, topPad = resize(cropped)
    finalImage = cv2.normalize(resized, None, 0.0, 1.0, cv2.NORM_MINMAX, cv2.CV_32F)

    transformInfo = {
        "crop_y": cropBox[1],
        "scale_factor": scaleFactor,
        "top_pad": topPad,
    }
    return finalImage, transformInfo

# transforms a coordinate with transformation info
def transform_ylabels (original_y, transformInfo):
    y_cropped = original_y - transformInfo["crop_y"]
    y_scaled = y_cropped * transformInfo["scale_factor"]
    y_final = y_scaled + transformInfo["top_pad"]
    return y_final

# adjusts the labels after image transformations
def update_coordinates(top_y, bottom_y, liquid_y, transformInfo):
    new_top = transform_ylabels(top_y, transformInfo)
    new_bottom = transform_ylabels(bottom_y, transformInfo)
    new_liquid = transform_ylabels(liquid_y, transformInfo)
    return new_top, new_bottom, new_liquid

# image names are "<uuid>_<session>.jpg"; uuids never contain "_", so split on the first one
def get_session_id (filename) :
    return os.path.splitext(os.path.basename(filename))[0].split("_", 1)[1]

# reads crop_boxes.csv into {session_id: (left, top, right, bottom)}, boxes stored as fractions of the image
def load_crop_boxes (path = CROP_BOXES_PATH) :
    if not os.path.exists(path) :
        return {}
    boxes = pd.read_csv(path, dtype = {"session_id": str}, keep_default_na = False)
    return {row.session_id: (row.left, row.top, row.right, row.bottom) for row in boxes.itertuples()}

# runs preprocessing for images in {filepath} csv, saving them to the dataset folder and preparing the dataset.csv for model training.
def preprocess_csv(filepath) :
    cropBoxes = load_crop_boxes()
    lb = pd.read_csv(filepath)
    required_columns = ["filename", "y_bottom", "y_top", "y_meniscus"]
    for col in required_columns :
        if col not in lb.columns :
            raise ValueError(f"Your CSV is missing a required column: '{col}'")

    columns = ["image_path", "session_id", "bottom_coordinate", "top_coordinate", "liquid_coordinate", "fill_percentage"]
    rows = []
    
    for row in lb.itertuples() :
        filename = row.filename
        image_path = os.path.join("images", filename)
        session_id = get_session_id(filename)
        
        # sessions with a known crop box use it, everything else falls back to edge detection
        try :
            preprocessed_image, transform_info = preprocess(image_path, cropBoxes.get(session_id), fractional = True)
        except (DetectionError, ValueError) as e :
            print(f" [IMAGE PROCESSING] Skipping {filename} : {e}")
            continue

        preproccessed_top, preproccessed_bottom, preproccessed_meniscus = update_coordinates(row.y_top, row.y_bottom, row.y_meniscus, transform_info)

        coords = (preproccessed_top, preproccessed_bottom, preproccessed_meniscus)

        # label far outside the image: probably a bad crop, so skip
        if not all(-LABEL_TOLERANCE <= c <= 128 + LABEL_TOLERANCE for c in coords) :
            print(f" [COORDINATE PROCESSING] Skipping {filename} : Coordinates out of cropped container bounds.")
            continue

        # label slightly outside: probably a labeling slip, so pull it back to the edge
        if not all(0 <= c <= 128 for c in coords) :
            print(f" [COORDINATE PROCESSING] Clamping {filename} : label slightly outside the crop {[round(c, 1) for c in coords]}")
        preproccessed_top, preproccessed_bottom, preproccessed_meniscus = (min(max(c, 0), 128) for c in coords)

        percentage = (preproccessed_meniscus - preproccessed_bottom) / (preproccessed_top - preproccessed_bottom) * 100
        percentage = max(0, min(100, percentage))

        pp_image_name = "pp_" + os.path.splitext(filename)[0] + ".png"
        pp_image_path = os.path.join("dataset", pp_image_name)
        os.makedirs("dataset", exist_ok = True)
        cv2.imwrite(pp_image_path, (preprocessed_image * 255).astype(np.uint8))

        complete_data = [pp_image_name, session_id, preproccessed_bottom, preproccessed_top, preproccessed_meniscus, percentage]
        rows.append(complete_data)
    
    df = pd.DataFrame(rows, columns = columns)
    df.to_csv("dataset/dataset.csv", index = False)
    return df

# testing preprocess function.
def TestImages () :
    path = input("Path of the image you would like to test?: ")
    processedImage, transformInfo = preprocess(path)

    filename =  "Image_" + datetime.now().strftime("%Y%m%d%H%M%S") + ".png"
    filename = os.path.join("testImages", filename)

    os.makedirs("testImages", exist_ok=True)
    cv2.imwrite(filename, (processedImage * 255).astype(np.uint8))

if __name__ == "__main__" :
    preprocess_csv("labels.csv")

import cv2
import numpy as np
import time
import os
from datetime import datetime

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
    print("lower: " + str(lower) + " | upper: " + str(upper))

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
        cv2.imwrite("houghMask_debug.png", lineMask)
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
    image = image[y:y+h, x:x+w]

    return image

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

    return bordered

# preprocessing function. Runs above functions and normalizes colors 0 - 1 instead of 1 - 256.
def preprocess (imagePath) :
    image = cv2.imread(imagePath)

    if image is None :
        raise ValueError("Could not open or find the image")

    image = crop_image_edge_detect(image)
    image = resize(image)
    finalImage = cv2.normalize(image, None, 0.0, 1.0, cv2.NORM_MINMAX, cv2.CV_32F)
    return finalImage

# testing preprocess function.
def TestImages () :
    path = input("Path of the image you would like to test?: ")
    processedImage = preprocess(path)

    filename =  "Image_" + datetime.now().strftime("%Y%m%d%H%M%S") + ".png"
    filename = os.path.join("testImages", filename)

    os.makedirs("testImages", exist_ok=True)
    cv2.imwrite(filename, (processedImage * 255).astype(np.uint8))


TestImages()















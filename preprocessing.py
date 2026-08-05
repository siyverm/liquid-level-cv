import cv2
import numpy as np

# Using canny, crops the image passed in to its edges. 
def crop_image_edge_detect (image) :
    if image is None :
        raise("Could not open or find the image")
    
    # creates grey copy of image 
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GREY)

    # reduce noise
    blur = cv2.GaussianBlur(gray, (5,5), 0)

    # detect edges (50 and 150 are variable thresholds, change them to adjust edge detection)
    edges = cv2.Canny(blur, 50, 150)

    contours, _ =  cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contours)
    
    image = image[y:y+h, x:x+w]












import cv2
import numpy as np
from preprocessing import crop_image_edge_detect

# feed images
# for each image, apply transformation
# pass in images from preprocessing
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) # path to windows camera
# Gy = [-1, -2, -1], [0, 0, 0], [1, 2, 1]

while True:
    ret, frame = cap.read()
    if not ret:
        break

    img = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # cropped_img = crop_image_edge_detect(img)
    sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)  # Vertical edges
    # sobely is only contributor to gradient magnitude bc we not worried about changes horizontally
    gradient_magnitude = cv2.convertScaleAbs(sobely)

    # display the processed frame
    cv2.imshow('Sobel edge detection', gradient_magnitude)
    # cv2.imshow('Windows Front Camera', img)

    # find y coordinate of water level
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    y = 0
    for pixel in height:
        if (gradient_magnitude[y + 1] < gradient_magnitude[y]) and (gradient_magnitude[y] > gradient_magnitude[y - 1])  :
            y = gradient_magnitude[y]
    
    print(y)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

import torch
import tensorflow as tf
import cv2

import os
import numpy as np
from matplotlib import pyplot as plt
import keras
from keras import layers
from keras import ops

# Initialize camera
cap = cv2.VideoCapture(0)
# Parsing through live video feed
while cap.isOpened():
    # Read frame
    ret, frame = cap.read()
    #Convert frame to grayscale
    img_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #According to OpenCV it's best to blur the image for better edge detection
    img_blur = cv2.GaussianBlur(img_gray, )
    #parse
    if cv2.waitKey(1) == ord('q'): #  if cv2.waitKey(1) & 0xFF == ord('q'):
        break

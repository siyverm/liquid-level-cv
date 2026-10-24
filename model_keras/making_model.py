import os
import numpy as np
import pandas as pd
import cv2
import tensorflow as tf
from keras import layers, Model, callbacks
import sys
import keras




# kernel that is applied over entire image
sobel_y = np.array([[1, 2, 1 ],
                    [0,   0,  0],
                    [-1,   -2,  -1]], dtype = "float32")
# modifies the kernel to be 2 kernels, one for detecting white into dark and other the inverse.
kernel = np.stack([sobel_y, -sobel_y], axis = -1) [:, :, np.newaxis, :]

MAX_WIDTH  = 500
MAX_HEIGHT = 500

# Creates the model itself, which uses keras to overlay the sobol matrix over the image
# and average pools into giving y values for when the sobel matrix is at maximum ()
def make_model (width = MAX_WIDTH, height = MAX_HEIGHT) :
    input = layers.Input(shape = (height, width, 1))
    # applies the kernel using a convolution layer (no learning)
    x = layers.Conv2D(2, kernel_size = 3, padding = "valid", use_bias = False, trainable = False, name = "sobel") (input)
    #idk if relu is actually needed. 
    x = layers.ReLU() (x)
    # reduce dimension, summing over all rows. 
    # x = layers.AveragePooling2D(pool_size = (1, width - 2)) (x)

    model = keras.Model(input, x)

    model.get_layer("sobel").set_weights([kernel])

    model.summary()
    model.save("detect_line.keras")

    return model

def predict (model, img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype("float32")   # (1080, 1920), for getting correct dimension into model
    profile = model.predict(gray[np.newaxis, :, :, np.newaxis])[0]

    profile = np.median(profile, axis = 1)

    height  = profile.shape[0]
    y = np.arange(height)
    margin = 0.05 * height
    dist_from_edge = np.minimum(y, height - 1 - y)
    w = np.clip(dist_from_edge / margin, 0, 1)
    w = 0.5 - 0.5 * np.cos(np.pi * w)
    profile = profile * w[:, None]

    return profile
  
def main () :

    model = make_model()

if __name__ == "__main__" :
    main()
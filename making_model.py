import os
import numpy as np
import pandas as pd
import cv2
import tensorflow as tf
from tensorflow.keras import layers, Model, callbacks
from sklearn.model_selection import train_test_split
import keras

sobel_y = np.array([[-1, -2, -1 ],
                    [0,   0,  0],
                    [1,   2,  1]], dtype = "float32")

kernel = np.stack([sobel_y, -sobel_y], axis = -1) [:, :, np.newaxis, :]

MAX_WIDTH  = 500
MAX_HEIGHT = 500

def make_model () :
    input = layers.Input(shape = (MAX_HEIGHT, MAX_WIDTH, 1))
    x = layers.Conv2D(2, kernel_size = 3, padding = "valid", use_bias = False, trainable = False, name = "sobel") (input)
    x = layers.ReLU() (x)
    x = layers.AveragePooling2D(pool_size = (1, MAX_WIDTH - 2)) (x)

    model = keras.Model(input, x)

    model.get_layer("sobel").set_weights([kernel])

    model.summary()
    model.save("detect_line.keras")

make_model()
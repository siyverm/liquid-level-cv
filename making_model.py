import os
import numpy as np
import pandas as pd
import cv2
import tensorflow as tf
from keras import layers, Model, callbacks
import sys
import keras

sobel_y = np.array([[-1, -2, -1 ],
                    [0,   0,  0],
                    [1,   2,  1]], dtype = "float32")

kernel = np.stack([sobel_y, -sobel_y], axis = -1) [:, :, np.newaxis, :]

MAX_WIDTH  = 500
MAX_HEIGHT = 500

def make_model (width = MAX_WIDTH, height = MAX_HEIGHT) :

    # for testing right now, we will allow the for user to specify the model dimensions
    input = layers.Input(shape = (height, width, 1))
    x = layers.Conv2D(2, kernel_size = 3, padding = "valid", use_bias = False, trainable = False, name = "sobel") (input)
    x = layers.ReLU() (x)
    x = layers.AveragePooling2D(pool_size = (1, width - 2)) (x)

    model = keras.Model(input, x)

    model.get_layer("sobel").set_weights([kernel])

    model.summary()
    model.save("detect_line.keras")

    return model

def predict (model, img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype("float32")   # (1080, 1920)
    profile = model.predict(gray[np.newaxis, :, :, np.newaxis])[0, :, 0, :] 
    return profile

def main () :
    cap = cv2.VideoCapture(0)
    ok, frame = cap.read()
    model = make_model(frame.shape[1], frame.shape[0])

    while True :
        ok, frame = cap.read()
        if not ok :
            break
        
        fill = predict(model, frame)
        print(fill);
        #cv2.imshow("ycoordinate (e = empty reference, q = quit)", draw(frame, y, fill))
        key = cv2.waitKey(1) & 0xFF
        if key == ord("e") :
            empty = frame.copy()
        elif key == ord("q") :
            break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__" :
    main()
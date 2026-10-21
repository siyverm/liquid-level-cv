import cv2
import numpy as np
import keras
import tensorflow as tf
from keras.models import load_model

def main():
    model = keras.models.load_model() # insert filepath here

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # use model to predict y coordinate of water level for the given frame
        # y = model.predict(img) 
        # returns two y values and an array of pixel values (size of array)
        # model outputs a matrix with 2 columns
        #   col 1 : light to dark
        #   col 2 : dark to light
        arr = model.predict(frame)
        y1 = np.max(arr[:, 0])
        y2 = np.max(arr[:, 1])
        y = (y1 + y2) / 2
        height = arr.shape[0]
        
        fill_percent = float(y / height) # 100 is a filler value (height of the crop box)
        print(fill_percent)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

def predict_volume(arr):
    y1 = np.argmax(arr[:, 0])
    y2 = np.argmax(arr[:, 1])
    print (y1, y2)
    y = (y1 + y2) / 2
    height = arr.shape[0]
    
    fill_percent = float(y / height) 
    fill_percent = 1 - fill_percent
    print(fill_percent)


if __name__ == "__main__" :
    main()
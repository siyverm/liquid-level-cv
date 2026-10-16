import cv2
import numpy as np
from tensorflow import keras
from keras.models import load_model
from preprocessing import crop_image_edge_detect, crop_image_fixed, resize, DetectionError
from preprocessing import preprocess


# model = keras.models.load_model() # insert filepath here

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # frame = preprocess(frame)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    # resize frame (beaker focus)
    img, scale = preprocess(frame)
    height = img.shape[0]

    # use model to predict y coordinate of water level for the given frame
    # y = model.predict(img) 

    fill_percent = float(y / (height*scale))
    print(fill_percent)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
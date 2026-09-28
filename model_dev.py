import os
import numpy as np
import pandas as pd
import cv2
import tensorflow as tf
from tensorflow.keras import layers, Model, callbacks
from sklearn.model_selection import train_test_split

# NOTE: RUNNING THIS RESULTS IN ERROR BECAUSE DATASET.CSV DOESN'T HOLD ANY DATA YET (see below)
# ValueError: With n_samples=0, test_size=None and train_size=0.75, the resulting train set will be empty. 
# Adjust any of the aforementioned parameters.

DATASET_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
# full path to CSV file with labels
MANIFEST_PATH = os.path.join(DATASET_ROOT, "dataset.csv")


IMG_WIDTH = 128 #filler value
IMG_HEIGHT = 128 #filler value
# How many images the model looks at during one training step
BATCH_SIZE = 8 #filler value
EPOCHS = 100

# when model is trained, it will be saved here
MODEL_OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.keras") # filler name for file

# Load CSV file
def load_manifest():
    df = pd.read_csv(MANIFEST_PATH)
    print(df.columns.tolist()) # some reason it says session_id doesn't exist in dataset.csv when it does so checking here
    # double check the csv has all the columns we expect
    required_columns = ["image_path", "session_id", "bottom_coordinate", "top_coordinate", "liquid_coordinate", "fill_percentage"] # same columns in dataset.csv
    # alterntively we can precompute the fill percentage to eliminate bottom, top, and liquid coordinate columns
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Your CSV is missing a required column: '{col}'")
    return df


def load_images_and_labels(df):
    # given a table of rows where each row is an image and its labels:
    # reads each file from the disk and converts it into a numpy array of numbers (0-255 pixel values)
    # scales pixel values down to a 0-1 range (models train better this way)
    # grabs the 3 labels for beaker size and water levels, then scales these down to a 0-1 range
    # returns 2 numpy arrays: all the images, and all the corresponding labels

    images = []
    labels = []

    for _, row in df.iterrows():
        image_path = os.path.join(DATASET_ROOT, row["image_path"])
        # read using openCV
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Could not find or open image: {image_path}")

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # make sure image size is the right size - script assumes images have already been resized
        img = img.astype("float32") / 255.0
        top = row["top_coordinate"] / IMG_HEIGHT
        bottom = row["bottom_coordinate"] / IMG_HEIGHT
        liquid = row["liquid_coordinate"] / IMG_HEIGHT

        images.append(img)
        labels.append([top, bottom, liquid])

    images = np.array(images, dtype="float32")
    labels = np.array(labels, dtype="float32")
    return images, labels

# split the data into train/val groups 
# keeps all rows from the same session together in the same group
# this way model can be validated through a session that it hasn't been trained on / seen before
def split_by_session(df, train_size=0.75, random_state=2):
    # Get the list of unique session IDs
    unique_sessions = df["session_id"].unique()
    # split sessions into train/val groups
    train_sessions, val_sessions = train_test_split(unique_sessions, train_size=train_size, random_state=random_state)
    # assign every row to a group based on which session it came from
    train_df = df[df["session_id"].isin(train_sessions)]
    val_df = df[df["session_id"].isin(val_sessions)]

    return train_df, val_df, train_sessions, val_sessions

# build neural network
def build_model():
    # CNNs are good for images because they can look at patches of an image and identify patterns
    # stacks multiple layers to build an understanding of more complex shapes
    inputs = layers.Input(shape=(IMG_HEIGHT, IMG_WIDTH, 3))
    x = layers.Conv2D(filters=8, kernel_size=3, strides=2, activation="relu", padding="same")(inputs)
    x = layers.Conv2D(filters=16, kernel_size=3, strides=2, activation="relu", padding="same")(x)
    x = layers.Conv2D(filters=32, kernel_size=3, strides=2, activation="relu", padding="same")(x)
    x = layers.GlobalAveragePooling2D()(x)
    # small, fully connected layer to combine extracted features before making final prediction
    x = layers.Dense(units=32, activation="relu")(x)
    # the final output has 3 numbers, predicted top, bottom, and liquid y coordinates (each scaled between 0 and 1)
    outputs = layers.Dense(units=3, activation="sigmoid")(x)
    model = Model(inputs=inputs, outputs=outputs)
    return model

# compile and trail the model
def train_model(model, train_images, train_labels, val_images, val_labels):
    model.compile(optimizer="adam", loss="mse", metrics=["mae"]) # double check these settings
    model.summary()

    training_callbacks = [callbacks.EarlyStopping(patience=15, restore_best_weights=True), callbacks.ReduceLROnPlateau(patience=6, factor=0.5),]

    model.fit(train_images, train_labels, validation_data=(val_images, val_labels), batch_size=BATCH_SIZE, epochs=EPOCHS, callbacks=training_callbacks,)
    return model

def main():
    df = load_manifest()
    # split into trail/val based on split column in CSV
    # train_df = df[df[SPLIT] == "train"]
    # val_df = df[df[SPLIT] == "val"] # update column name - fade this
    
    train_df, val_df, train_sessions, val_sessions = split_by_session(df, train_size=0.75, random_state=2)

    # maybe print something for validation that this works
    # train_sessions and val_sessions are values for validation purposes

    # print(f"Found {len(train_df)} training images and {len(val_df)} validation images.")
    # if len(train_df) < 100:
    #   print("WARNING: This is a small dataset. Expect limited generalization "
    #         "until more training images are collected.")

    train_images, train_labels = load_images_and_labels(train_df)
    val_images, val_labels = load_images_and_labels(val_df)

    model = build_model()
    model = train_model(model, train_images, train_labels, val_images, val_labels)
    model.save(MODEL_OUT_PATH)
    #print(f"Training complete, model saved to: {MODEL_OUT_PATH}")

if __name__ == "__main__":
    main()

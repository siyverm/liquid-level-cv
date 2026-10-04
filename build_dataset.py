# Rebuilds the training dataset from a Label Studio export in one step:
# export JSON -> labels.csv -> preprocessed images + dataset/dataset.csv
# Run from the project folder: python build_dataset.py <label-studio-export>.json

import glob
import json
import os
import sys
from read_labels import processLabels
from preprocessing import preprocess_csv

def build_dataset (exportPath) :
    # clear old preprocessed images so removed or relabeled images don't linger
    for oldImage in glob.glob(os.path.join("dataset", "pp_*.png")) :
        os.remove(oldImage)

    with open(exportPath) as file :
        exported = len(json.load(file))

    print("Reading labels...")
    labeled = processLabels(exportPath)

    print("Preprocessing images...")
    dataset = preprocess_csv("labels.csv")

    print(f"\n{exported} tasks in export -> {labeled} in labels.csv -> {len(dataset)} in dataset/dataset.csv")
    if len(dataset) < exported :
        print(f"{exported - len(dataset)} image(s) were dropped, see the messages above for why.")

if __name__ == "__main__" :
    if len(sys.argv) != 2 :
        print("Usage: python build_dataset.py <label-studio-export>.json")
        sys.exit(1)
    build_dataset(sys.argv[1])

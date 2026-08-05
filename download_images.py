import requests
import csv
import time
import os

DIRECTORY = "images"
os.makedirs(DIRECTORY, exist_ok=True)

def downloadImage (url, maxVol, currVol, row) :
    filename = 'image_' + str(row) + '_' + str(maxVol) + '_' + str(currVol) + '.jpg'
    filename = os.path.join(DIRECTORY, filename)
    with requests.get(url , stream = True) as response :
        response.raise_for_status()

        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192) :
                file.write(chunk)
    
    print('Downloaded: ' +  filename)
    time.sleep(1)

def getFileName () :
    return input("What is the name of the file containing images to download?: ")

with open(getFileName(), mode = 'r', encoding = 'utf-8') as file:
    reader = csv.DictReader(file)

    index = 2
    for row in reader:
        try:
            downloadImage(row['1_Photo_of_Container'], row['2_What_is_the_total_'], 
                        row['3_What_is_the_height'],index)
        except requests.exceptions.RequestException as e:
            print('Download of image in row: ' + str(index) + ' failed due to ' + str(e))
        index = index + 1

    print('\nFinished the download of ' + str(index - 2)  + ' images!')
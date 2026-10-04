# Downloads every photo listed in an Epicollect CSV export into the images folder.
# Safe to rerun after a new export: photos already downloaded are skipped.

import requests
import csv
import time
import os

# where downloaded photos are saved
DIRECTORY = "images"
os.makedirs(DIRECTORY, exist_ok=True)

# Downloads one photo, named "<uuid>_<session>.jpg" so it stays linked to its Epicollect entry.
# Returns True if it downloaded the photo, False if it was already there.
def downloadImage (url, uiud, ssid) :
    filename = f"{uiud}_{ssid}.jpg"
    filename = os.path.join(DIRECTORY, filename)

    # already downloaded on an earlier run, nothing to do
    if os.path.exists(filename) :
        return False

    # download to a temporary name so a failed download never looks like a finished photo
    temp = filename + ".part"
    # stream = True downloads the photo in pieces instead of holding it all in memory
    with requests.get(url , stream = True) as response :
        # turns an HTTP error (404, 500...) into an exception so it's counted as a failure
        response.raise_for_status()

        with open(temp, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192) :
                file.write(chunk)
    os.replace(temp, filename)   # only becomes a .jpg once fully downloaded

    print('Downloaded: ' +  filename)
    # pause between downloads so we don't flood Epicollect's server
    time.sleep(1)
    return True

# asks for the Epicollect CSV export to read
def getFileName () :
    return input("What is the name of the file containing images to download?: ")

# utf-8-sig strips the hidden BOM Epicollect puts at the start of its exports,
# otherwise the first column would be read as "﻿ec5_uuid" instead of "ec5_uuid"
with open(getFileName(), mode = 'r', encoding = 'utf-8-sig') as file:
    # reads each row as a dictionary keyed by column name
    reader = csv.DictReader(file)

    # row 1 of the CSV is the header, so the first photo is on row 2 (matches the row number in a spreadsheet)
    index = 2
    downloaded = 0
    skipped = 0
    failed = 0
    for row in reader:
        # column names come from the Epicollect form; the number prefix is the question's position
        try:
            if downloadImage(row['1_Photo_of_Container'], row['ec5_uuid'], row['2_SessionID']) :
                downloaded += 1
            else :
                skipped += 1
        # a failed download is reported and the rest keep going; rerun later to retry it
        except requests.exceptions.RequestException as e:
            print('Download of image in row: ' + str(index) + ' failed due to ' + str(e))
            failed += 1
        index = index + 1

    print('\nDownloaded ' + str(downloaded) + ' new images, skipped ' + str(skipped) + ' already downloaded, ' + str(failed) + ' failed.')
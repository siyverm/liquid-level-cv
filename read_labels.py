# Serves the purpose of reading JSON output of Label Studio and writing to csv

import json, csv, os, sys

# reads json and writes to csv, returns how many images were written
def processLabels (filePath) :
    with open(filePath) as file :
        tasks = json.load(file)

    written = 0
    with open(file = "labels.csv", mode = "w", newline = "") as out :
        w = csv.writer(out)
        w.writerow(["filename", "y_top", "y_bottom", "y_meniscus"])
        for t in tasks :
            # ignore annotations that were skipped in Label Studio
            anns = [a for a in t["annotations"] if not a.get("was_cancelled")]
            if not anns :
                continue
            pts = {}
            for r in anns[0]["result"] :
                label = r["value"]["keypointlabels"][0]
                y_px = r["value"]["y"] / 100 * r["original_height"]
                pts.setdefault(label, []).append(y_px)
            if any(len(pts.get(k,[])) != 1 for k in ("top", "bottom", "meniscus")) :
                print("Bad label set:", t["data"]["image"], {k: len(v) for k, v in pts.items()})
                continue

            fname = os.path.basename(t["data"]["image"])
            w.writerow([fname, pts["top"][0], pts["bottom"][0], pts["meniscus"][0]])
            written += 1

    return written

if __name__ == "__main__" :
    if len(sys.argv) != 2 :
        print("Usage: python read_labels.py <label-studio-export>.json")
        sys.exit(1)
    processLabels(sys.argv[1])



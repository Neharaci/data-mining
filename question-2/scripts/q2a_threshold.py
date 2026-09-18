import csv
import glob
import re

DATA = r"C:\Users\ub02-glab-079\Downloads\data_2\data_2"
NOTICE_FILES = glob.glob(DATA + r"\notices\*.csv")
LABEL_FILE = DATA + r"\labelled_pairs.csv"


def normalize(text):
    text = text.lower()

    text = re.sub(
        r'\b(?:ref|reference|tender reference|nit)[-\s:#]*[a-z0-9/-]+\b',
        ' ',
        text
    )

    for phrase in ["tender notice", "e-tender", "e tender", "nit", "corrigendum"]:
        text = text.replace(phrase, " ")

    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def tokens(text):
    return set(normalize(text).split())


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


notices = {}

for filename in NOTICE_FILES:
    with open(filename, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            notices[row["notice_id"]] = row


with open(LABEL_FILE, "r", encoding="utf-8-sig", newline="") as f:
    pairs = list(csv.DictReader(f))


scores = []

for p in pairs:
    a = notices[p["notice_id_a"]]
    b = notices[p["notice_id_b"]]

    ta = tokens(a["title"] + " " + a["body"])
    tb = tokens(b["title"] + " " + b["body"])

    scores.append((jaccard(ta, tb), p["label"]))


print("THRESHOLD ANALYSIS")
print("=" * 70)
print("Threshold | TP | FP | FN | TN | Precision | Recall | False Merge Rate")
print("-" * 70)

best = None

for i in range(50, 91):
    threshold = i / 100

    tp = sum(s >= threshold and label == "same" for s, label in scores)
    fp = sum(s >= threshold and label == "different" for s, label in scores)
    fn = sum(s < threshold and label == "same" for s, label in scores)
    tn = sum(s < threshold and label == "different" for s, label in scores)

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    false_merge_rate = fp / (fp + tn) if fp + tn else 0

    print(
        f"{threshold:9.2f} | {tp:2d} | {fp:2d} | {fn:2d} | {tn:3d} | "
        f"{precision:9.3f} | {recall:6.3f} | {false_merge_rate:16.3f}"
    )
import csv
import glob
import re
from collections import Counter

DATA = r"C:\Users\ub02-glab-079\Downloads\data_2\data_2"
NOTICE_FILES = glob.glob(DATA + r"\notices\*.csv")
LABEL_FILE = DATA + r"\labelled_pairs.csv"


def normalize(text):
    text = text.lower()

    # Remove tender reference numbers
    text = re.sub(r'\b(?:ref|reference|tender reference|nit)[-\s:#]*[a-z0-9/-]+\b', ' ', text)

    # Remove common portal/tender boilerplate
    boilerplate = [
        "tender notice",
        "e-tender",
        "e tender",
        "nit",
        "corrigendum",
    ]
    for phrase in boilerplate:
        text = text.replace(phrase, " ")

    # Keep words/numbers, normalize whitespace
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def word_tokens(text):
    return set(normalize(text).split())


def char_ngrams(text, n=3):
    text = normalize(text).replace(" ", "_")
    if len(text) < n:
        return {text}
    return {text[i:i+n] for i in range(len(text)-n+1)}


def jaccard(a, b):
    if not a and not b:
        return 1.0
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


results = []

for p in pairs:
    a = notices[p["notice_id_a"]]
    b = notices[p["notice_id_b"]]

    text_a = a["title"] + " " + a["body"]
    text_b = b["title"] + " " + b["body"]

    word_sim = jaccard(word_tokens(text_a), word_tokens(text_b))
    char_sim = jaccard(char_ngrams(text_a), char_ngrams(text_b))

    results.append({
        "label": p["label"],
        "word_jaccard": word_sim,
        "char3_jaccard": char_sim
    })


def summarize(field):
    same = [r[field] for r in results if r["label"] == "same"]
    different = [r[field] for r in results if r["label"] == "different"]

    print("\n", field)
    print("-" * 50)
    print("Same pairs:")
    print("  count:", len(same))
    print("  mean :", sum(same) / len(same))
    print("  min  :", min(same))
    print("  max  :", max(same))

    print("Different pairs:")
    print("  count:", len(different))
    print("  mean :", sum(different) / len(different))
    print("  min  :", min(different))
    print("  max  :", max(different))


print("Q2(a) REPRESENTATION EXPERIMENT")
print("=" * 60)
print("Notices loaded:", len(notices))
print("Labelled pairs:", len(pairs))
print("Same:", sum(p["label"] == "same" for p in pairs))
print("Different:", sum(p["label"] == "different" for p in pairs))

summarize("word_jaccard")
summarize("char3_jaccard")
import csv
import glob
import re
import hashlib
import time
from collections import Counter
from datasketch import MinHash, MinHashLSH

DATA = r"C:\Users\ub02-glab-079\Downloads\data_2\data_2"

NUM_PERM = 128
THRESHOLD = 0.55

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

records = []

print("Loading full corpus...")

for filename in glob.glob(DATA + r"\notices\*.csv"):
    with open(filename, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            records.append({
                "id": row["notice_id"],
                "portal": row["portal_id"],
                "tokens": tokens(row["title"] + " " + row["body"])
            })

print("Notices:", len(records))

print("Building LSH index...")

lsh = MinHashLSH(threshold=THRESHOLD, num_perm=NUM_PERM)

for r in records:
    mh = MinHash(num_perm=NUM_PERM)

    for token in r["tokens"]:
        mh.update(token.encode())

    r["mh"] = mh
    lsh.insert(r["id"], mh)

print("Generating candidates...")

portal_of = {r["id"]: r["portal"] for r in records}

candidate_count = Counter()
total_candidates = 0
seen = set()

start = time.perf_counter()

for r in records:
    result = lsh.query(r["mh"])

    for other in result:
        if other == r["id"]:
            continue

        pair = tuple(sorted((r["id"], other)))

        if pair in seen:
            continue

        seen.add(pair)

        portal = portal_of[r["id"]]
        candidate_count[portal] += 1
        total_candidates += 1

elapsed = time.perf_counter() - start

print()
print("================================")
print("Q2(e) CANDIDATE SKEW")
print("================================")
print("Total candidates:", total_candidates)
print("Candidate generation time:", round(elapsed, 3), "seconds")
print()

print("TOP PORTALS BY CANDIDATE WORK")
print("==============================")

cumulative = 0

for portal, count in candidate_count.most_common(20):

    cumulative += count

    print(
        f"{portal:6} "
        f"{count:10} candidates "
        f"{100*count/total_candidates:6.2f}% "
        f"cumulative={100*cumulative/total_candidates:6.2f}%"
    )

print()
print("================================")
print("Q2(e) COMPLETE")
print("================================")
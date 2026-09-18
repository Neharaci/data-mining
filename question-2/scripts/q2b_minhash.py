import csv
import glob
import re
import hashlib

DATA = r"C:\Users\ub02-glab-079\Downloads\data_2\data_2"

def normalize(text):
    text = text.lower()
    text = re.sub(r'\b(?:ref|reference|tender reference|nit)[-\s:#]*[a-z0-9/-]+\b', ' ', text)

    for phrase in ["tender notice", "e-tender", "e tender", "nit", "corrigendum"]:
        text = text.replace(phrase, " ")

    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def get_tokens(text):
    return set(normalize(text).split())

def exact_jaccard(a, b):
    return len(a & b) / len(a | b) if a or b else 0

def hash_token(token, seed):
    return int.from_bytes(
        hashlib.blake2b(
            f"{seed}:{token}".encode(),
            digest_size=8
        ).digest(),
        "big"
    )

def minhash(tokens, k):
    return [
        min(hash_token(t, seed) for t in tokens)
        for seed in range(k)
    ]

# Load notices
notices = {}

for file in glob.glob(DATA + r"\notices\*.csv"):
    with open(file, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            notices[row["notice_id"]] = row

# Load labelled pairs
with open(DATA + r"\labelled_pairs.csv", encoding="utf-8-sig", newline="") as f:
    pairs = list(csv.DictReader(f))

# Only notices needed for labelled-pair experiment
needed = set()

for p in pairs:
    needed.add(p["notice_id_a"])
    needed.add(p["notice_id_b"])

tokens = {}

for nid in needed:
    row = notices[nid]
    tokens[nid] = get_tokens(row["title"] + " " + row["body"])

print("Q2(b) MINHASH SPACE/ACCURACY EXPERIMENT")
print("=" * 65)
print("Total corpus notices:", len(notices))
print("Trusted labelled pairs:", len(pairs))
print("Unique notices used in experiment:", len(tokens))
print()

for k in [32, 64, 128, 256]:

    signatures = {
        nid: minhash(tok, k)
        for nid, tok in tokens.items()
    }

    errors = []
    false_merges = 0
    missed_same = 0

    for p in pairs:

        a = p["notice_id_a"]
        b = p["notice_id_b"]

        exact = exact_jaccard(tokens[a], tokens[b])

        estimated = sum(
            x == y
            for x, y in zip(signatures[a], signatures[b])
        ) / k

        errors.append(abs(exact - estimated))

        if p["label"] == "different" and estimated >= 0.65:
            false_merges += 1

        if p["label"] == "same" and estimated < 0.65:
            missed_same += 1

    print("Signature size:", k)
    print("Storage per notice:", k, "hash values")
    print("Mean absolute error:", round(sum(errors) / len(errors), 6))
    print("Maximum absolute error:", round(max(errors), 6))
    print("False merges at 0.65:", false_merges)
    print("Missed same pairs at 0.65:", missed_same)
    print("-" * 65)

print("Experiment complete.")
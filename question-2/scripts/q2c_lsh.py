import csv
import glob
import re
import time
from datasketch import MinHash, MinHashLSH

DATA = r"C:\Users\ub02-glab-079\Downloads\data_2\data_2"
NOTICE_FILES = glob.glob(DATA + r"\notices\*.csv")
LABEL_FILE = DATA + r"\labelled_pairs.csv"

NUM_PERM = 128
DECISION_THRESHOLD = 0.65


def normalize(text):
    text = text.lower()

    text = re.sub(
        r'\b(?:ref|reference|tender reference|nit)[-\s:#]*[a-z0-9/-]+\b',
        ' ',
        text
    )

    for phrase in [
        "tender notice",
        "e-tender",
        "e tender",
        "nit",
        "corrigendum"
    ]:
        text = text.replace(phrase, " ")

    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def get_tokens(text):
    return set(normalize(text).split())


def exact_jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ------------------------------------------------------------
# Load notices
# ------------------------------------------------------------

print("Loading notices...")

notices = {}

for filename in NOTICE_FILES:
    with open(filename, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            notices[row["notice_id"]] = row

print("Notices loaded:", len(notices))


# ------------------------------------------------------------
# Load labelled pairs
# ------------------------------------------------------------

with open(LABEL_FILE, encoding="utf-8-sig", newline="") as f:
    labelled_pairs = list(csv.DictReader(f))

print("Labelled pairs:", len(labelled_pairs))


# ------------------------------------------------------------
# Create MinHash signatures
# ------------------------------------------------------------

print("Creating 128-hash MinHash signatures...")

start = time.time()

minhashes = {}

for i, (notice_id, row) in enumerate(notices.items(), 1):

    tokens = get_tokens(row["title"] + " " + row["body"])

    m = MinHash(num_perm=NUM_PERM)

    for token in tokens:
        m.update(token.encode("utf-8"))

    minhashes[notice_id] = m

    if i % 2000 == 0:
        print("  processed:", i)

signature_time = time.time() - start

print("Signature creation time:", round(signature_time, 2), "seconds")
print()


# ------------------------------------------------------------
# Test LSH operating points
# ------------------------------------------------------------

print("LSH OPERATING-POINT EXPERIMENT")
print("=" * 80)

for threshold in [0.50, 0.55, 0.60, 0.65]:

    start = time.time()

    lsh = MinHashLSH(
        threshold=threshold,
        num_perm=NUM_PERM
    )

    for notice_id, m in minhashes.items():
        lsh.insert(notice_id, m)

    # Generate candidate pairs
    candidate_pairs = set()

    for notice_id, m in minhashes.items():
        candidates = lsh.query(m)

        for other in candidates:
            if other != notice_id:
                pair = tuple(sorted((notice_id, other)))
                candidate_pairs.add(pair)

    retrieval_time = time.time() - start

    # Evaluate labelled-pair survival
    same_total = 0
    same_survived = 0
    different_total = 0
    different_survived = 0

    for p in labelled_pairs:

        pair = tuple(sorted((p["notice_id_a"], p["notice_id_b"])))

        survived = pair in candidate_pairs

        if p["label"] == "same":
            same_total += 1
            if survived:
                same_survived += 1

        else:
            different_total += 1
            if survived:
                different_survived += 1

    recall = same_survived / same_total

    # Candidate rate relative to all possible pairs
    total_possible = len(notices) * (len(notices) - 1) // 2
    candidate_rate = len(candidate_pairs) / total_possible

    print("LSH threshold:", threshold)
    print("Candidate pairs:", len(candidate_pairs))
    print("All possible pairs:", total_possible)
    print("Candidate fraction:", round(candidate_rate, 6))
    print("Candidate reduction:", round((1 - candidate_rate) * 100, 3), "%")
    print("Same pairs surviving:", same_survived, "/", same_total)
    print("True-pair survival rate:", round(recall, 4))
    print(
        "Different labelled pairs surviving:",
        different_survived,
        "/",
        different_total
    )
    print("LSH retrieval time:", round(retrieval_time, 2), "seconds")
    print("-" * 80)


print("LSH experiment complete.")
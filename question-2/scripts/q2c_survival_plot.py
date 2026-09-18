import csv
import re
import matplotlib.pyplot as plt

DATA = r"C:\Users\ub02-glab-079\Downloads\data_2\data_2"

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

def word_tokens(text):
    return set(normalize(text).split())

def jaccard(a, b):
    if not a and not b:
        return 1.0

    return len(a & b) / len(a | b)

# Load notices
notices = {}

import glob

for filename in glob.glob(DATA + r"\notices\*.csv"):
    with open(filename, encoding="utf-8-sig", newline="") as f:

        for row in csv.DictReader(f):

            notices[row["notice_id"]] = word_tokens(
                row["title"] + " " + row["body"]
            )

# Load labelled pairs
pairs = []

with open(
    DATA + r"\labelled_pairs.csv",
    encoding="utf-8-sig",
    newline=""
) as f:

    for row in csv.DictReader(f):

        a = notices[row["notice_id_a"]]
        b = notices[row["notice_id_b"]]

        similarity = jaccard(a, b)

        pairs.append(
            (similarity, row["label"])
        )

# Create similarity bins
bins = [
    (0.20, 0.30),
    (0.30, 0.40),
    (0.40, 0.50),
    (0.50, 0.60),
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 0.90),
    (0.90, 1.01)
]

x = []
y = []

for low, high in bins:

    same = [
        s for s, label in pairs
        if label == "same" and low <= s < high
    ]

    different = [
        s for s, label in pairs
        if label == "different" and low <= s < high
    ]

    total = len(same) + len(different)

    if total == 0:
        continue

    # Probability that a pair is a true duplicate
    survival = len(same) / total

    x.append((low + min(high, 1.0)) / 2)
    y.append(survival)

    print(
        f"{low:.2f}-{min(high,1.0):.2f}: "
        f"same={len(same)}, "
        f"different={len(different)}, "
        f"same_probability={survival:.4f}"
    )

# Plot
plt.figure(figsize=(8, 5))

plt.plot(
    x,
    y,
    marker="o",
    label="P(same | similarity bin)"
)

plt.axvline(
    0.55,
    linestyle="--",
    label="LSH operating point = 0.55"
)

plt.xlabel("True normalized-word Jaccard similarity")
plt.ylabel("Probability pair is labelled SAME")
plt.title("Candidate Retrieval Operating Point")
plt.legend()
plt.grid(True)

plt.tight_layout()

output = r"C:\Users\ub02-glab-079\Desktop\data-mining\question-2\evidence\q2c_survival_plot.png"

plt.savefig(output, dpi=200)

print()
print("Plot saved to:")
print(output)
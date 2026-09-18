import csv
import glob
from collections import Counter

DATA = r"C:\Users\ub02-glab-079\Downloads\data_2\data_2\notices"

portal_counts = Counter()
file_counts = Counter()

for filename in glob.glob(DATA + r"\*.csv"):
    with open(filename, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        count = 0

        for row in reader:
            portal_counts[row["portal_id"]] += 1
            count += 1

        file_counts[filename.split("\\")[-1]] = count

total = sum(portal_counts.values())

print("TOTAL NOTICES:", total)
print()

print("PORTAL DISTRIBUTION")
print("===================")

cumulative = 0

for portal, count in portal_counts.most_common():
    cumulative += count

    pct = 100 * count / total
    cumulative_pct = 100 * cumulative / total

    print(
        f"{portal:6} {count:5} notices "
        f"{pct:6.2f}% "
        f"cumulative={cumulative_pct:6.2f}%"
    )

print()
print("CONCENTRATION")
print("=============")

for n in [1, 5, 10, 20]:
    amount = sum(x for _, x in portal_counts.most_common(n))
    print(
        f"Top {n:2} portals: "
        f"{amount:5} notices = "
        f"{100 * amount / total:.2f}%"
    )

print()
print("FILE DISTRIBUTION")
print("=================")

for filename, count in sorted(file_counts.items()):
    print(filename, count)

print()
print("Q2(e) SKEW ANALYSIS COMPLETE")
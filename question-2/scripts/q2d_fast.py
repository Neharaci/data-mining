import csv
import glob
import re
import hashlib
import psycopg

DATA = r"C:\Users\ub02-glab-079\Downloads\data_2\data_2"

BANDS = 32
ROWS = 4

def normalize(text):
    text = text.lower()
    text = re.sub(
        r'\b(?:ref|reference|tender reference|nit)[-\s:#]*[a-z0-9/-]+\b',
        ' ',
        text
    )
    for x in ["tender notice", "e-tender", "e tender", "nit", "corrigendum"]:
        text = text.replace(x, " ")
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def bucket(text, band):
    value = f"{band}:{text}".encode()
    return int.from_bytes(
        hashlib.blake2b(value, digest_size=8).digest(),
        "big",
        signed=True
    )

# Get only notices participating in the trusted labelled experiment
ids = set()

with open(DATA + r"\labelled_pairs.csv", encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        ids.add(r["notice_id_a"])
        ids.add(r["notice_id_b"])

print("Trusted notices:", len(ids))

notice_rows = []
bucket_rows = []

for filename in glob.glob(DATA + r"\notices\*.csv"):
    with open(filename, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["notice_id"] not in ids:
                continue

            text = normalize(r["title"] + " " + r["body"])

            notice_rows.append(
                (r["notice_id"], text)
            )

            for band in range(BANDS):
                b = bucket(text, band)
                bucket_rows.append(
                    (band, b, r["notice_id"])
                )

print("Notice rows:", len(notice_rows))
print("Bucket rows:", len(bucket_rows))

conn = psycopg.connect(
    "dbname=annapurna host=localhost user=annapurna password=annapurna"
)

cur = conn.cursor()

cur.execute("TRUNCATE notice_minhash, lsh_buckets;")

# Store normalized representation as the persistent signature payload.
with cur.copy(
    "COPY notice_minhash (notice_id, signature) FROM STDIN"
) as cp:
    for notice_id, text in notice_rows:
        cp.write_row((notice_id, text.encode()))

with cur.copy(
    "COPY lsh_buckets (band, bucket_hash, notice_id) FROM STDIN"
) as cp:
    for row in bucket_rows:
        cp.write_row(row)

conn.commit()

cur.execute("ANALYZE notice_minhash")
cur.execute("ANALYZE lsh_buckets")
conn.commit()

cur.execute("SELECT COUNT(*) FROM notice_minhash")
print("PostgreSQL notice rows:", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM lsh_buckets")
print("PostgreSQL bucket rows:", cur.fetchone()[0])

cur.close()
conn.close()

print("Q2(d) FAST LOAD COMPLETE")
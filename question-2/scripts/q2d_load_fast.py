import csv
import glob
import re
import hashlib
import psycopg

DATA = r"C:\Users\ub02-glab-079\Downloads\data_2\data_2"

NUM_PERM = 128
BANDS = 32
ROWS_PER_BAND = 4

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

def get_tokens(text):
    return set(normalize(text).split())

def hash_token(token, seed):
    return int.from_bytes(
        hashlib.blake2b(
            f"{seed}:{token}".encode(),
            digest_size=8
        ).digest(),
        "big"
    )

def minhash(tokens):
    return [
        min(hash_token(token, seed) for token in tokens)
        for seed in range(NUM_PERM)
    ]

def bucket_hash(values):
    data = ",".join(map(str, values)).encode()
    return int.from_bytes(
        hashlib.blake2b(data, digest_size=8).digest(),
        "big",
        signed=True
    )

print("Reading notices and generating 128-hash signatures...")

notice_rows = []
bucket_rows = []

for filename in glob.glob(DATA + r"\notices\*.csv"):
    with open(filename, encoding="utf-8-sig", newline="") as f:

        for row in csv.DictReader(f):

            notice_id = row["notice_id"]
            tokens = get_tokens(row["title"] + " " + row["body"])

            signature = minhash(tokens)

            signature_bytes = ",".join(
                map(str, signature)
            ).encode()

            notice_rows.append(
                (notice_id, signature_bytes)
            )

            for band in range(BANDS):
                start = band * ROWS_PER_BAND
                end = start + ROWS_PER_BAND

                bucket = bucket_hash(
                    signature[start:end]
                )

                bucket_rows.append(
                    (band, bucket, notice_id)
                )

print("Notices processed:", len(notice_rows))
print("LSH bucket rows prepared:", len(bucket_rows))

conn = psycopg.connect(
    "dbname=annapurna host=localhost user=annapurna password=annapurna"
)

cur = conn.cursor()

print("Clearing previous Q2(d) data...")

cur.execute("TRUNCATE notice_minhash, lsh_buckets;")

print("Bulk loading MinHash signatures...")

with cur.copy(
    "COPY notice_minhash (notice_id, signature) FROM STDIN"
) as copy:

    for notice_id, signature in notice_rows:
        copy.write_row((notice_id, signature))

print("Bulk loading LSH buckets...")

with cur.copy(
    "COPY lsh_buckets (band, bucket_hash, notice_id) FROM STDIN"
) as copy:

    for band, bucket, notice_id in bucket_rows:
        copy.write_row((band, bucket, notice_id))

conn.commit()

print("Running ANALYZE...")

cur.execute("ANALYZE notice_minhash;")
cur.execute("ANALYZE lsh_buckets;")

cur.execute("SELECT COUNT(*) FROM notice_minhash;")
notice_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM lsh_buckets;")
bucket_count = cur.fetchone()[0]

print()
print("====================================")
print("Q2(d) RELATIONAL LOAD COMPLETE")
print("====================================")
print("PostgreSQL notice rows:", notice_count)
print("PostgreSQL LSH bucket rows:", bucket_count)
print("Hash functions:", NUM_PERM)
print("Bands:", BANDS)
print("Rows per band:", ROWS_PER_BAND)
print("====================================")

cur.close()
conn.close()

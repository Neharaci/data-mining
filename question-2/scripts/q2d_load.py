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


# ------------------------------------------------------------
# Load notices and generate signatures
# ------------------------------------------------------------

print("Loading notices and generating signatures...")

records = []

for filename in glob.glob(DATA + r"\notices\*.csv"):

    with open(filename, encoding="utf-8-sig", newline="") as f:

        for row in csv.DictReader(f):

            tokens = get_tokens(
                row["title"] + " " + row["body"]
            )

            signature = minhash(tokens)

            records.append(
                (row["notice_id"], signature)
            )

print("Notices processed:", len(records))


# ------------------------------------------------------------
# Insert into PostgreSQL
# ------------------------------------------------------------

conn = psycopg.connect(
    "dbname=annapurna host=localhost user=annapurna password=annapurna"
)

cur = conn.cursor()

cur.execute("TRUNCATE notice_minhash, lsh_buckets;")

print("Loading PostgreSQL...")


for notice_id, signature in records:

    # Store signature as comma-separated text bytes
    signature_bytes = ",".join(
        map(str, signature)
    ).encode()

    cur.execute(
        """
        INSERT INTO notice_minhash
        (notice_id, signature)
        VALUES (%s, %s)
        """,
        (notice_id, signature_bytes)
    )

    # 32 bands × 4 rows = 128 hash values
    for band in range(BANDS):

        start = band * ROWS_PER_BAND
        end = start + ROWS_PER_BAND

        bucket = bucket_hash(
            signature[start:end]
        )

        cur.execute(
            """
            INSERT INTO lsh_buckets
            (band, bucket_hash, notice_id)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (band, bucket, notice_id)
        )


conn.commit()

cur.execute("SELECT COUNT(*) FROM notice_minhash;")
notice_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM lsh_buckets;")
bucket_count = cur.fetchone()[0]

print("PostgreSQL notice rows:", notice_count)
print("PostgreSQL LSH bucket rows:", bucket_count)

cur.close()
conn.close()

print("Q2(d) load complete.")
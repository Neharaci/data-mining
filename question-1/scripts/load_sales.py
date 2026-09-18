import os
import re
import io
import hashlib
from pathlib import Path

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


# =========================================================
# CONFIGURATION
# =========================================================

SOURCE_DIR = Path(
    os.environ.get("SOURCE_DIR", "/exam/data/sales")
)

MINIO_ENDPOINT = os.environ.get(
    "MINIO_ENDPOINT",
    "http://minio:9000"
)

MINIO_ACCESS_KEY = os.environ.get(
    "MINIO_ACCESS_KEY",
    "minioadmin"
)

MINIO_SECRET_KEY = os.environ.get(
    "MINIO_SECRET_KEY",
    "minioadmin"
)

BUCKET = "annapurna"

# SALES_S01_20240101.csv
# SALES_S01_20240101__R1.csv
# SALES_S01_20240101__R2.csv

FILE_PATTERN = re.compile(
    r"^SALES_(S\d{2})_(\d{8})(?:__R\d+)?\.(csv|parquet)$",
    re.IGNORECASE
)

# According to the billing rules, these count as revenue.
REVENUE_TYPES = {
    "SALE",
    "RETURN",
    "DISCOUNT",
    "VOID",
}


# =========================================================
# MINIO CONNECTION
# =========================================================

s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1",
)


def ensure_bucket():
    try:
        s3.head_bucket(Bucket=BUCKET)
        print(f"Bucket '{BUCKET}' already exists.")
    except Exception:
        s3.create_bucket(Bucket=BUCKET)
        print(f"Created bucket '{BUCKET}'.")


# =========================================================
# FILENAME PARSING
# =========================================================

def parse_filename(path):

    match = FILE_PATTERN.match(path.name)

    if not match:
        raise ValueError(
            f"Unexpected sales filename: {path.name}"
        )

    store_id = match.group(1)

    # IMPORTANT:
    # The filename date is the business date.
    business_date = pd.to_datetime(
        match.group(2),
        format="%Y%m%d"
    ).date()

    return store_id, business_date


# =========================================================
# COLUMN NORMALIZATION
# =========================================================

def normalize_columns(df):

    # Remove BOM and whitespace
    df.columns = [
        str(c).replace("\ufeff", "").strip()
        for c in df.columns
    ]

    aliases = {
        "bill_no": [
            "bill_no",
            "bill",
            "billnumber"
        ],

        "line_no": [
            "line_no",
            "lineno",
            "line"
        ],

        "product_code": [
            "product_code",
            "item_code",
            "product",
            "item"
        ],

        "qty": [
            "qty",
            "quantity"
        ],

        "unit_price": [
            "unit_price",
            "rate",
            "price"
        ],

        "line_type": [
            "line_type",
            "type"
        ],

        "ts": [
            "ts",
            "txn_time",
            "timestamp"
        ],
    }

    rename = {}

    lower_columns = {
        str(c).lower().strip(): c
        for c in df.columns
    }

    for target, possible_names in aliases.items():

        for name in possible_names:

            if name in lower_columns:

                rename[
                    lower_columns[name]
                ] = target

                break

    df = df.rename(columns=rename)

    required = [
        "bill_no",
        "line_no",
        "product_code",
        "qty",
        "unit_price",
        "line_type",
        "ts",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            f"Missing columns: {missing}. "
            f"Actual columns: {list(df.columns)}"
        )

    return df[required]


# =========================================================
# READ ONE SALES FILE
# =========================================================

def read_sales_file(path):

    store_id, business_date = parse_filename(path)

    # -------------------------
    # Parquet
    # -------------------------

    if path.suffix.lower() == ".parquet":

        df = pd.read_parquet(path)

    # -------------------------
    # CSV
    # -------------------------

    else:

        with open(
            path,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as f:

            sample = f.read(4096)
            f.seek(0)

            # S06-S09 use semicolon.
            # Other CSV files use comma.
            delimiter = ";"

            if ";" not in sample:

                delimiter = ","

            df = pd.read_csv(
                f,
                sep=delimiter
            )

    # Normalize different vendor schemas
    df = normalize_columns(df)

    # Store ID comes from filename
    df["store_id"] = store_id

    # Filename date is the business date
    df["business_date"] = pd.to_datetime(
        business_date
    )

    # Keep source filename for auditability
    df["source_file"] = path.name

    # -------------------------
    # Normalize data types
    # -------------------------

    df["bill_no"] = (
        df["bill_no"]
        .astype(str)
        .str.strip()
    )

    df["line_no"] = pd.to_numeric(
        df["line_no"],
        errors="raise"
    ).astype("int64")

    df["product_code"] = (
        df["product_code"]
        .astype(str)
        .str.strip()
    )

    df["qty"] = pd.to_numeric(
        df["qty"],
        errors="raise"
    )

    df["unit_price"] = pd.to_numeric(
        df["unit_price"],
        errors="raise"
    )

    df["line_type"] = (
        df["line_type"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    return df


# =========================================================
# MAIN LOAD
# =========================================================

def main():

    print("========================================")
    print("ANNAPURNA SALES INGESTION")
    print("========================================")

    print(f"Source directory: {SOURCE_DIR}")

    ensure_bucket()

    # Find CSV and Parquet files
    files = sorted(
        [
            p
            for p in SOURCE_DIR.iterdir()
            if p.is_file()
            and p.name.lower().endswith(
                (".csv", ".parquet")
            )
        ],
        key=lambda p: p.name
    )

    print(f"Files discovered: {len(files)}")

    if not files:

        raise RuntimeError(
            "No sales files found."
        )

    # =====================================================
    # READ ALL FILES
    # =====================================================

    frames = []

    for i, path in enumerate(
        files,
        start=1
    ):

        if i == 1 or i % 250 == 0:

            print(
                f"Reading {i}/{len(files)}: "
                f"{path.name}"
            )

        df = read_sales_file(path)

        frames.append(df)

    sales = pd.concat(
        frames,
        ignore_index=True
    )

    print()
    print(
        f"Rows before deduplication: "
        f"{len(sales)}"
    )

    # =====================================================
    # IDEMPOTENT DEDUPLICATION
    # =====================================================

    # Vendor-defined safe line key:
    # (bill_no, line_no)

    sales = sales.sort_values(
        [
            "bill_no",
            "line_no",
            "source_file"
        ]
    )

    duplicate_rows = sales.duplicated(
        subset=[
            "bill_no",
            "line_no"
        ],
        keep=False
    ).sum()

    print(
        f"Rows involved in duplicate keys: "
        f"{duplicate_rows}"
    )

    # Keep one deterministic copy of each line
    sales = sales.drop_duplicates(
        subset=[
            "bill_no",
            "line_no"
        ],
        keep="first"
    )

    print(
        f"Rows after deduplication: "
        f"{len(sales)}"
    )

    # =====================================================
    # REVENUE
    # =====================================================

    sales["revenue_amount"] = 0.0

    revenue_mask = sales[
        "line_type"
    ].isin(REVENUE_TYPES)

    sales.loc[
        revenue_mask,
        "revenue_amount"
    ] = (
        sales.loc[
            revenue_mask,
            "qty"
        ]
        *
        sales.loc[
            revenue_mask,
            "unit_price"
        ]
    )

    # TAX and TENDER therefore remain zero revenue.

    # =====================================================
    # PARTITION COLUMNS
    # =====================================================

    sales["year"] = (
        sales["business_date"]
        .dt.year
        .astype(int)
    )

    sales["month"] = (
        sales["business_date"]
        .dt.month
        .astype(int)
    )

    # =====================================================
    # DETERMINISTIC ORDER
    # =====================================================

    sales = sales.sort_values(
        [
            "business_date",
            "store_id",
            "bill_no",
            "line_no"
        ]
    ).reset_index(drop=True)

    # =====================================================
    # WRITE ONE PARQUET PER STORE/MONTH
    # =====================================================

    total_uploaded = 0

    grouped = sales.groupby(
        [
            "store_id",
            "year",
            "month"
        ],
        sort=True
    )

    for (
        (store_id, year, month),
        group
    ) in grouped:

        group = group.drop(
            columns=[
                "year",
                "month"
            ]
        )

        table = pa.Table.from_pandas(
            group,
            preserve_index=False
        )

        buffer = io.BytesIO()

        pq.write_table(
            table,
            buffer,
            compression="snappy"
        )

        buffer.seek(0)

        # Partition layout:
        #
        # raw/sales/
        #   store_id=S01/
        #     year=2024/
        #       month=10/
        #         sales.parquet

        key = (
            f"raw/sales/"
            f"store_id={store_id}/"
            f"year={year}/"
            f"month={month:02d}/"
            f"sales.parquet"
        )

        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=buffer.getvalue()
        )

        total_uploaded += len(group)

        print(
            f"Uploaded {key} | "
            f"rows={len(group)} | "
            f"bytes={buffer.getbuffer().nbytes}"
        )

    # =====================================================
    # CANONICAL CHECKSUM
    # =====================================================

    canonical = sales[
        [
            "bill_no",
            "line_no",
            "store_id",
            "business_date",
            "product_code",
            "qty",
            "unit_price",
            "line_type",
            "revenue_amount",
        ]
    ].copy()

    canonical["business_date"] = (
        canonical[
            "business_date"
        ]
        .dt.strftime("%Y-%m-%d")
    )

    checksum_text = canonical.to_csv(
        index=False,
        lineterminator="\n"
    )

    checksum = hashlib.sha256(
        checksum_text.encode("utf-8")
    ).hexdigest()

    # =====================================================
    # FINAL SUMMARY
    # =====================================================

    print()
    print("========================================")
    print("LOAD SUMMARY")
    print("========================================")
    print(f"Source files       : {len(files)}")
    print(f"Rows after dedup   : {len(sales)}")
    print(f"Rows uploaded      : {total_uploaded}")
    print(f"Canonical SHA256   : {checksum}")
    print("Object store       : MinIO")
    print("Bucket             : annapurna")
    print("Partitioning       : store_id / year / month")
    print("========================================")


if __name__ == "__main__":
    main()
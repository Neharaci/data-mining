import duckdb
import psycopg


# =========================================================
# DuckDB
# =========================================================

con = duckdb.connect()

con.execute("INSTALL httpfs;")
con.execute("LOAD httpfs;")

con.execute("""
SET s3_endpoint='minio:9000';
SET s3_access_key_id='minioadmin';
SET s3_secret_access_key='minioadmin';
SET s3_use_ssl=false;
SET s3_url_style='path';
""")


# =========================================================
# PostgreSQL
# =========================================================

pg = psycopg.connect(
    "host=postgres "
    "port=5432 "
    "dbname=annapurna "
    "user=annapurna "
    "password=annapurna"
)

cur = pg.cursor()


# =========================================================
# IMPORTANT:
# Rebuild fact table from scratch.
# =========================================================

print("Clearing previous fact table...")

cur.execute("""
TRUNCATE fact_sales RESTART IDENTITY;
""")

pg.commit()


# =========================================================
# Read all sales from MinIO
# =========================================================

print("Reading sales from MinIO using DuckDB...")

sales_query = """
SELECT
    bill_no,
    line_no,
    store_id,
    product_code,
    business_date,
    qty,
    unit_price,
    line_type,
    revenue_amount
FROM read_parquet(
    's3://annapurna/raw/sales/store_id=*/year=*/month=*/sales.parquet',
    hive_partitioning=true
)
ORDER BY
    business_date,
    store_id,
    bill_no,
    line_no
"""

sales = con.execute(
    sales_query
).fetchall()

print(
    f"Rows read from MinIO: {len(sales)}"
)


# =========================================================
# Insert ALL source lines
#
# LEFT JOIN is intentional:
# non-product lines must not disappear.
# =========================================================

insert_sql = """
INSERT INTO fact_sales (
    bill_no,
    line_no,
    store_sk,
    product_sk,
    date_key,
    qty,
    unit_price,
    line_type,
    revenue_amount
)
SELECT
    %s,
    %s,
    ds.store_sk,
    dp.product_sk,
    TO_CHAR(%s::date, 'YYYYMMDD')::integer,
    %s,
    %s,
    %s,
    %s
FROM dim_store ds
LEFT JOIN dim_product dp
    ON dp.product_code = %s
   AND %s::date BETWEEN dp.valid_from
                    AND dp.valid_to
WHERE ds.store_id = %s
ON CONFLICT (bill_no, line_no) DO NOTHING
"""


for i, row in enumerate(
    sales,
    start=1
):

    (
        bill_no,
        line_no,
        store_id,
        product_code,
        business_date,
        qty,
        unit_price,
        line_type,
        revenue_amount
    ) = row

    cur.execute(
        insert_sql,
        (
            bill_no,
            line_no,
            business_date,
            qty,
            unit_price,
            line_type,
            revenue_amount,
            product_code,
            business_date,
            store_id,
        )
    )

    if i % 100000 == 0:

        print(
            f"Inserted {i} rows..."
        )


pg.commit()


# =========================================================
# Dashboard aggregate
# =========================================================

print(
    "Building dashboard daily aggregate..."
)

cur.execute("""
TRUNCATE dashboard_revenue_daily;

INSERT INTO dashboard_revenue_daily (
    store_sk,
    category_id,
    date_key,
    revenue
)
SELECT
    fs.store_sk,
    COALESCE(
        dp.category_id,
        'C00'
    ) AS category_id,
    fs.date_key,
    SUM(fs.revenue_amount)
FROM fact_sales fs
LEFT JOIN dim_product dp
    ON fs.product_sk = dp.product_sk
GROUP BY
    fs.store_sk,
    COALESCE(
        dp.category_id,
        'C00'
    ),
    fs.date_key;
""")

pg.commit()


# =========================================================
# Validation
# =========================================================

cur.execute(
    "SELECT COUNT(*) FROM fact_sales"
)

fact_count = cur.fetchone()[0]


cur.execute(
    "SELECT COUNT(*) FROM dashboard_revenue_daily"
)

dashboard_count = cur.fetchone()[0]


cur.execute("""
SELECT
    line_type,
    COUNT(*)
FROM fact_sales
GROUP BY line_type
ORDER BY line_type
""")

line_counts = cur.fetchall()


print()
print("========================================")
print("CORRECTED FACT LOAD SUMMARY")
print("========================================")
print(
    f"MinIO rows read       : {len(sales)}"
)
print(
    f"PostgreSQL fact rows  : {fact_count}"
)
print(
    f"Dashboard rows        : {dashboard_count}"
)

print()
print("Fact rows by line type:")

for line_type, count in line_counts:

    print(
        f"  {line_type:<10} : {count}"
    )

print("========================================")


cur.close()
pg.close()
con.close()
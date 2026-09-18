-- =========================================================
-- Q1(c) DASHBOARD STAR SCHEMA
-- =========================================================

DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_category;
DROP TABLE IF EXISTS dim_store;

-- ---------------------------------------------------------
-- Store dimension
-- ---------------------------------------------------------

CREATE TABLE dim_store (
    store_sk BIGSERIAL PRIMARY KEY,
    store_id TEXT NOT NULL UNIQUE,
    store_name TEXT NOT NULL,
    address_line TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    region TEXT NOT NULL
);

INSERT INTO dim_store (
    store_id,
    store_name,
    address_line,
    city,
    state,
    region
)
SELECT
    store_id,
    store_name,
    address_line,
    city,
    state,
    region
FROM stores;


-- ---------------------------------------------------------
-- Category dimension
-- ---------------------------------------------------------

CREATE TABLE dim_category (
    category_id TEXT PRIMARY KEY,
    category_name TEXT NOT NULL,
    department TEXT NOT NULL,
    gst_rate NUMERIC(4,3) NOT NULL
);

INSERT INTO dim_category (
    category_id,
    category_name,
    department,
    gst_rate
)
SELECT
    category_id,
    category_name,
    department,
    gst_rate
FROM product_categories;

INSERT INTO dim_category (
    category_id,
    category_name,
    department,
    gst_rate
)
VALUES (
    'C00',
    'Unallocated / Bill-Level',
    'Other',
    0.000
);


-- ---------------------------------------------------------
-- Product dimension
--
-- IMPORTANT:
-- product_code is NOT unique.
-- product_sk identifies the actual product version.
-- ---------------------------------------------------------

CREATE TABLE dim_product (
    product_sk BIGINT PRIMARY KEY,
    product_code TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category_id TEXT NOT NULL,
    brand TEXT,
    pack_size TEXT,
    uom TEXT,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL
);

INSERT INTO dim_product
SELECT
    product_sk,
    product_code,
    product_name,
    category_id,
    brand,
    pack_size,
    uom,
    valid_from,
    valid_to,
    is_current
FROM products;


-- ---------------------------------------------------------
-- Date dimension
-- ---------------------------------------------------------

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day_of_week INTEGER NOT NULL,
    day_name TEXT NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    year INTEGER NOT NULL
);

INSERT INTO dim_date
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER AS date_key,
    d::DATE AS full_date,
    EXTRACT(ISODOW FROM d)::INTEGER AS day_of_week,
    TO_CHAR(d, 'FMDay') AS day_name,
    EXTRACT(MONTH FROM d)::INTEGER AS month,
    TO_CHAR(d, 'FMMonth') AS month_name,
    EXTRACT(YEAR FROM d)::INTEGER AS year
FROM generate_series(
    DATE '2024-01-01',
    DATE '2024-12-31',
    INTERVAL '1 day'
) AS x(d);


-- ---------------------------------------------------------
-- Sales fact table
--
-- Store/product/date are represented by keys instead of
-- repeating descriptive attributes.
-- ---------------------------------------------------------

CREATE TABLE fact_sales (
    sales_line_id BIGSERIAL PRIMARY KEY,
    bill_no TEXT NOT NULL,
    line_no BIGINT NOT NULL,
    store_sk BIGINT NOT NULL REFERENCES dim_store(store_sk),
    product_sk BIGINT,
    date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    qty NUMERIC NOT NULL,
    unit_price NUMERIC NOT NULL,
    line_type TEXT NOT NULL,
    revenue_amount NUMERIC(14,2) NOT NULL,
    UNIQUE (bill_no, line_no)
);

CREATE INDEX ix_fact_sales_store
    ON fact_sales(store_sk);

CREATE INDEX ix_fact_sales_product
    ON fact_sales(product_sk);

CREATE INDEX ix_fact_sales_date
    ON fact_sales(date_key);

CREATE INDEX ix_fact_sales_store_date
    ON fact_sales(store_sk, date_key);

CREATE INDEX ix_fact_sales_product_date
    ON fact_sales(product_sk, date_key);


-- ---------------------------------------------------------
-- Daily dashboard aggregate
-- ---------------------------------------------------------

CREATE TABLE dashboard_revenue_daily (
    store_sk BIGINT NOT NULL REFERENCES dim_store(store_sk),
    category_id TEXT NOT NULL REFERENCES dim_category(category_id),
    date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    revenue NUMERIC(14,2) NOT NULL,
    PRIMARY KEY (
        store_sk,
        category_id,
        date_key
    )
);

CREATE INDEX ix_dashboard_revenue_daily_date
    ON dashboard_revenue_daily(date_key);

CREATE INDEX ix_dashboard_revenue_daily_store
    ON dashboard_revenue_daily(store_sk);

CREATE INDEX ix_dashboard_revenue_daily_category
    ON dashboard_revenue_daily(category_id);

ANALYZE;
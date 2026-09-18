DROP TABLE IF EXISTS lsh_buckets;
DROP TABLE IF EXISTS notice_minhash;

CREATE TABLE notice_minhash (
    notice_id VARCHAR(20) PRIMARY KEY,
    signature BYTEA NOT NULL
);

CREATE TABLE lsh_buckets (
    band INTEGER NOT NULL,
    bucket_hash BIGINT NOT NULL,
    notice_id VARCHAR(20) NOT NULL,
    PRIMARY KEY (band, bucket_hash, notice_id)
);

CREATE INDEX idx_lsh_bucket
ON lsh_buckets (band, bucket_hash);

CREATE INDEX idx_lsh_notice
ON lsh_buckets (notice_id);

ANALYZE notice_minhash;
ANALYZE lsh_buckets;
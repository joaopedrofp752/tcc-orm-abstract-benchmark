DROP TABLE IF EXISTS benchmark_payload;

CREATE TABLE benchmark_payload (
    id BIGSERIAL PRIMARY KEY,
    payload_data TEXT NOT NULL
);

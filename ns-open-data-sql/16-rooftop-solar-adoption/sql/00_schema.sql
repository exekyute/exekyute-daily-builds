-- 00_schema: raw landing table. Everything lands as text; typing happens in
-- 02_transform so a malformed cell cannot fail the load.

CREATE OR REPLACE TABLE solar_raw (
    partial_postal_code  VARCHAR,
    total_dc_capacity_kw VARCHAR,
    year_installed       VARCHAR
);

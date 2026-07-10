-- 00_schema.sql
-- Question this step answers: what shape does the data take before any analysis runs?
-- Defines a staging table for the raw snapshot, a cleaned table, and the result mart.
-- No rows are touched here; this only declares structure.

CREATE OR REPLACE TABLE raw_licenses (
    license_number  VARCHAR,
    license_type    VARCHAR,
    establishment   VARCHAR,
    street_address  VARCHAR,
    city_town       VARCHAR,
    province        VARCHAR,
    postal_code     VARCHAR,
    location        VARCHAR
);

CREATE OR REPLACE TABLE clean_licenses (
    license_number  VARCHAR,
    license_type    VARCHAR,
    community       VARCHAR
);

CREATE OR REPLACE TABLE license_density (
    community                VARCHAR,
    community_total_licenses BIGINT,
    community_rank           BIGINT,
    license_type             VARCHAR,
    type_count               BIGINT,
    type_share_pct           DOUBLE,
    is_dominant_type         BIGINT
);

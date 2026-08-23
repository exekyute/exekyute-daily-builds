-- 00_schema.sql
-- Raw landing table for the committed snapshot, plus the one-row constants
-- table every later step reads. All snapshot columns land as text; typing
-- happens in 02_transform.sql so bad values are counted there, not silently
-- swallowed by the reader.

CREATE OR REPLACE TABLE raw_readings (
    site_id           VARCHAR,
    datetimeutc       VARCHAR,
    air_temperature   VARCHAR,
    relative_humidity VARCHAR,
    avg_wind_speed    VARCHAR
);

-- Every threshold in the audit lives here. Nothing downstream hardcodes a
-- number; spec.md justifies each one. Window bounds are literal DATE
-- constants, never CURRENT_DATE, so the golden output does not drift.
CREATE OR REPLACE TABLE audit_constants AS
SELECT
    DATE '2024-01-01'  AS window_start,         -- inclusive
    DATE '2024-01-15'  AS window_end_excl,      -- exclusive
    3                  AS gap_k,                -- gap when interval > K x cadence
    30                 AS frozen_run_min_readings,
    30                 AS min_intervals_for_mode,
    99.0               AS uptime_flag_pct,
    -50.0              AS air_temp_min_c,
    45.0               AS air_temp_max_c,
    1.0                AS rh_min_pct,
    100.0              AS rh_max_pct,
    0.0                AS wind_min,
    200.0              AS wind_max;

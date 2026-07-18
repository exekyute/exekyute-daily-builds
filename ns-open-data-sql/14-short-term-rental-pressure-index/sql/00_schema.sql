-- 00_schema.sql
-- Question this step answers: what shape does the data take before any analysis runs?
-- Defines a staging table for the raw snapshot, a long-format cleaned table, a
-- cross-check table, and the result mart. No rows are touched here; this only
-- declares structure.

CREATE OR REPLACE TABLE raw_registry (
    census_division                   VARCHAR,
    commercial_short_term_rental      VARCHAR,
    whole_home_primary_residence      VARCHAR,
    traditional_tourist_accommodation VARCHAR
);

-- one row per (region, category): the wide source unpivoted
CREATE OR REPLACE TABLE clean_registrations (
    region        VARCHAR,
    category      VARCHAR,
    registrations BIGINT
);

-- the source ships its own 'Total' row; 02_transform inserts one boolean here
-- comparing that row to the sum of the 18 division rows. The CHECK makes a
-- mismatch abort the run instead of passing silently.
CREATE OR REPLACE TABLE check_totals (
    source_total_matches_division_sum BOOLEAN CHECK (source_total_matches_division_sum)
);

CREATE OR REPLACE TABLE str_pressure (
    region                   VARCHAR,
    total_registrations      BIGINT,
    pct_of_province          DOUBLE,
    rank_by_count            BIGINT,
    commercial_count         BIGINT,
    whole_home_count         BIGINT,
    traditional_count        BIGINT,
    commercial_share_pct     DOUBLE,
    rank_by_commercial_share BIGINT,
    dominant_type            VARCHAR
);

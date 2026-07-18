-- 01_load.sql
-- Question this step answers: what are the raw rows, exactly as pulled from the portal?
-- Loads the pinned dated snapshot from data/raw into the staging table. Every column is
-- read as text (all_varchar) so nothing is silently retyped or dropped on the way in.
-- The path is relative to the project folder; run.py sets that as the working directory.

INSERT INTO raw_registry
SELECT
    census_division,
    commercial_short_term_rental,
    whole_home_primary_residence,
    traditional_tourist_accommodation
FROM read_csv_auto(
    'data/raw/ns_str-registry_2026-07-06.csv',
    header = true,
    all_varchar = true
);

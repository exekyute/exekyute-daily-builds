-- 01_load.sql
-- Question this step answers: what are the raw rows, exactly as pulled from the portal?
-- Loads the pinned dated snapshot from data/raw into the staging table. Every column is
-- read as text (all_varchar) so nothing is silently retyped or dropped on the way in.
-- The path is relative to the project folder; run.py sets that as the working directory.

INSERT INTO raw_licenses
SELECT
    license_number,
    license_type,
    establishment,
    street_address,
    city_town,
    province,
    postal_code,
    location
FROM read_csv_auto(
    'data/raw/ns_liquor-licenses_2026-07-05.csv',
    header = true,
    all_varchar = true
);

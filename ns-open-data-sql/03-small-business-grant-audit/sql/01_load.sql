-- 01_load.sql
-- Loads the pinned snapshot into raw_grants. The glob matches the single dated
-- file in data/raw, so the snapshot date never has to be hard-coded here.
-- all_varchar keeps every field as published text, so nothing is coerced on read.

INSERT INTO raw_grants
SELECT
    year,
    ns_small_business,
    type_of_business,
    received_small_business_impact,
    received_small_business
FROM read_csv(
    'data/raw/ns_small-business-grant_*.csv',
    header = true,
    all_varchar = true
);

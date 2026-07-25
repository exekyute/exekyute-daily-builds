-- 01_load.sql
-- Question this step answers: what are the raw rows, exactly as pulled from the portal?
-- Loads the pinned dated snapshot from data/raw into the staging table. Every column is
-- read as text (all_varchar) so nothing is silently retyped or dropped on the way in.
-- The path is relative to the project folder; run.py sets that as the working directory.

INSERT INTO raw_coops
SELECT
    registry_id,
    co_op_name,
    incorporation_year,
    address,
    town,
    province_state,
    postal_code,
    non_profit_n_for_profit_p,
    type
FROM read_csv_auto(
    'data/raw/ns_coop-registry_2026-07-06.csv',
    header = true,
    all_varchar = true
);

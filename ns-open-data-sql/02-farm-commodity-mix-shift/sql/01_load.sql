-- 01_load.sql
-- Question this step answers: what did the source publish, exactly as it stands?
-- Loads the pinned CSV snapshot into raw_farm with no changes. The path is relative to the
-- project folder, which run.py sets as the working directory before running any SQL.

INSERT INTO raw_farm
SELECT commodity, fiscal_year, total_of_registered_farms
FROM read_csv_auto('data/raw/ns_farm-commodity-mix_2026-07-05.csv', header = true);

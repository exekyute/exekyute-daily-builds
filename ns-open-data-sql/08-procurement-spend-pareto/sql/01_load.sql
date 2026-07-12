-- 01_load.sql
-- Question this step answers: how do we get the pinned snapshot into the staging table?
-- Reads the dated CSV snapshot from data/raw as all-text (header on) and appends it to
-- raw_tenders. The path is relative, so run.py changes into this folder before running.

DELETE FROM raw_tenders;

INSERT INTO raw_tenders
SELECT
  tender_id, entity, goods, service, construction,
  tender_start_date, tender_close_date, tender_description,
  awarded_date, awarded_amount, vendor
FROM read_csv_auto(
  'data/raw/ns_awarded-tenders_2026-07-05.csv',
  header = true,
  all_varchar = true
);

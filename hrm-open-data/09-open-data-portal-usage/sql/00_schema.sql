-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is
-- the raw shape of the committed snapshot?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. The committed snapshot is already aggregated
-- to one row per dataset and month (see SOURCE.md for how the 639,108 live rows
-- were rolled to this grain). Its columns land as VARCHAR here; casting happens
-- in 02_transform.

DROP TABLE IF EXISTS oda_raw;
DROP TABLE IF EXISTS oda_clean;
DROP TABLE IF EXISTS oda_month;
DROP TABLE IF EXISTS mart_usage_monthly;
DROP TABLE IF EXISTS mart_usage_by_dataset;
DROP TABLE IF EXISTS headline;

CREATE TABLE oda_raw (
  dataset     VARCHAR,
  month_start VARCHAR,
  usage       VARCHAR
);

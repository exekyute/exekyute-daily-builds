-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is
-- the raw shape of the source file?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. The raw columns are all VARCHAR because the
-- Socrata CSV delivers every field as text; casting happens in 02_transform.

DROP TABLE IF EXISTS mva_raw;
DROP TABLE IF EXISTS mva_clean;
DROP TABLE IF EXISTS mva_yearly;
DROP TABLE IF EXISTS offence_window;
DROP TABLE IF EXISTS offence_window_ranked;
DROP TABLE IF EXISTS convictions_ranked;
DROP TABLE IF EXISTS headline;

CREATE TABLE mva_raw (
  offence_statute VARCHAR,
  description     VARCHAR,
  year_convicted  VARCHAR,
  convictions     VARCHAR
);

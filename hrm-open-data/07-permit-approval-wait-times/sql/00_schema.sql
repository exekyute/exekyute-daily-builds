-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is
-- the raw shape of the source file?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. The raw columns are all VARCHAR because the
-- Hub CSV delivers every field as text; casting happens in 02_transform.

DROP TABLE IF EXISTS pt_raw;
DROP TABLE IF EXISTS pt_mart;
DROP TABLE IF EXISTS processing_summary;
DROP TABLE IF EXISTS headline;

CREATE TABLE pt_raw (
  permit_number            VARCHAR,
  issuance_stage           VARCHAR,
  jurisdictional_breakdown VARCHAR,
  total_occurrence         VARCHAR,
  total_duration           VARCHAR
);

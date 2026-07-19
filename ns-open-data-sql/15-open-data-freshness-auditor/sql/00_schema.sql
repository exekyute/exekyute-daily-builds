-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is
-- the raw shape of the source file?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. The raw columns are all VARCHAR because the
-- Socrata CSV delivers every field as text; casting happens in 02_transform.

DROP TABLE IF EXISTS catalogue_raw;
DROP TABLE IF EXISTS params;
DROP TABLE IF EXISTS catalogue_clean;
DROP TABLE IF EXISTS asset_audit;
DROP TABLE IF EXISTS bucket_summary;
DROP TABLE IF EXISTS by_category;
DROP TABLE IF EXISTS by_owner;
DROP TABLE IF EXISTS worst_offenders;
DROP TABLE IF EXISTS freshness_audit;
DROP TABLE IF EXISTS headline;

CREATE TABLE catalogue_raw (
  name                       VARCHAR,
  description                VARCHAR,
  detailedmetadata_department VARCHAR,
  type                       VARCHAR,
  category                   VARCHAR,
  tags                       VARCHAR,
  url                        VARCHAR,
  api_endpoint               VARCHAR,
  last_metadata_updated_date VARCHAR,
  last_data_updated_date     VARCHAR
);

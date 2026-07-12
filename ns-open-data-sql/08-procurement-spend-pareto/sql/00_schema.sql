-- 00_schema.sql
-- Question this step answers: what raw shape do we load before any cleaning?
-- Defines the staging table that mirrors the Socrata CSV exactly (every column text,
-- so nothing is coerced or dropped on the way in). Derived tables are built later with
-- CREATE OR REPLACE TABLE AS in 02 and 03.

DROP TABLE IF EXISTS raw_tenders;
DROP TABLE IF EXISTS clean_awards;
DROP TABLE IF EXISTS vendor_totals;
DROP TABLE IF EXISTS vendor_pareto;

CREATE TABLE raw_tenders (
  tender_id          VARCHAR,
  entity             VARCHAR,
  goods              VARCHAR,
  service            VARCHAR,
  construction       VARCHAR,
  tender_start_date  VARCHAR,
  tender_close_date  VARCHAR,
  tender_description VARCHAR,
  awarded_date       VARCHAR,
  awarded_amount     VARCHAR,
  vendor             VARCHAR
);

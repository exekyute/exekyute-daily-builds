-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is the
-- raw shape of the committed snapshot?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. The snapshot is the compact server-side grouped
-- pull (one row per tax group, summary group, rate code, rate description, and
-- bill rate percentage), not the 1.25M raw account lines. Every raw column is
-- VARCHAR because the pull is read as text; casting happens in 02_transform.

DROP TABLE IF EXISTS tax_raw;
DROP TABLE IF EXISTS tax_clean;
DROP TABLE IF EXISTS mart_tax_group;
DROP TABLE IF EXISTS mart_tax_class;
DROP TABLE IF EXISTS tax_group_summary;
DROP TABLE IF EXISTS taxable_by_class;
DROP TABLE IF EXISTS rate_effective;
DROP TABLE IF EXISTS headline;

CREATE TABLE tax_raw (
  tax_group            VARCHAR,
  tax_summary_group    VARCHAR,
  rate_code            VARCHAR,
  rate_description     VARCHAR,
  bill_rate_percentage VARCHAR,
  account_count        VARCHAR,
  residential_taxable  VARCHAR,
  commercial_taxable   VARCHAR,
  resource_taxable     VARCHAR,
  bill_value           VARCHAR,
  bill_amount          VARCHAR
);

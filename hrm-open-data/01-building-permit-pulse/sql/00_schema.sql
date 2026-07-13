-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is
-- the raw shape of the committed snapshot?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. The raw columns are all VARCHAR because the
-- committed snapshot is plain text; casting happens in 02_transform.

DROP TABLE IF EXISTS permits_raw;
DROP TABLE IF EXISTS permit_mart;
DROP TABLE IF EXISTS params;
DROP TABLE IF EXISTS permits_by_year_worktype;
DROP TABLE IF EXISTS district_units_running_total;
DROP TABLE IF EXISTS permits_by_community;
DROP TABLE IF EXISTS headline;

CREATE TABLE permits_raw (
  source_object_id        VARCHAR,
  permit_number           VARCHAR,
  date_of_permit_issuance VARCHAR,
  estimated_project_value VARCHAR,
  work_type               VARCHAR,
  primary_work_scope      VARCHAR,
  permit_status           VARCHAR,
  community               VARCHAR,
  district                VARCHAR,
  net_new_units           VARCHAR,
  number_of_storeys       VARCHAR,
  type_of_structure       VARCHAR,
  latitude                VARCHAR,
  longitude               VARCHAR
);

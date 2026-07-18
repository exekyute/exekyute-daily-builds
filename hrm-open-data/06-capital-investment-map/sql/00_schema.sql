-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is
-- the raw shape of one capital-project record?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. The text fields land as VARCHAR and the budget
-- year lands as VARCHAR too, so every type cast happens in one place,
-- 02_transform. The point coordinates land as DOUBLE: they are numeric geometry
-- read from the GeoJSON point, not text.

DROP TABLE IF EXISTS cap_raw;
DROP TABLE IF EXISTS cap_clean;
DROP TABLE IF EXISTS counts_by_category_year;
DROP TABLE IF EXISTS counts_by_asset_type;
DROP TABLE IF EXISTS category_ranking;
DROP TABLE IF EXISTS headline;

CREATE TABLE cap_raw (
  objectid   BIGINT,
  proj_no    VARCHAR,
  proj_name  VARCHAR,
  loc_id     VARCHAR,
  loc_desc   VARCHAR,
  work_desc  VARCHAR,
  category   VARCHAR,
  asset_type VARCHAR,
  year       VARCHAR,
  lon        DOUBLE,
  lat        DOUBLE
);

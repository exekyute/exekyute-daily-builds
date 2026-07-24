-- 00_schema.sql
-- Question this step answers: what engine features and tables does the pipeline
-- use, and what is the starting state?
-- Winter maintenance is three separate layers, two polygon and one line, so the
-- pipeline reads GeoJSON with DuckDB's spatial extension. INSTALL and LOAD run
-- once here in the shared connection; every later step can then call ST_Read,
-- ST_Area_Spheroid, and the geometry writers. Drop every table so a re-run
-- starts from a clean, repeatable state. The raw tables are created by ST_Read
-- in 01_load, so they are only dropped here, not declared.

INSTALL spatial;
LOAD spatial;

DROP TABLE IF EXISTS street_raw;
DROP TABLE IF EXISTS sidewalk_raw;
DROP TABLE IF EXISTS ice_raw;
DROP TABLE IF EXISTS street_clean;
DROP TABLE IF EXISTS sidewalk_clean;
DROP TABLE IF EXISTS ice_clean;
DROP TABLE IF EXISTS ice_by_priority;
DROP TABLE IF EXISTS coverage_summary;
DROP TABLE IF EXISTS headline;

-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is the
-- raw shape of the committed snapshot?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. The snapshot is the whole HRM Building Energy
-- Usage table, one row per meter reading period. Every raw column is VARCHAR
-- because the CSV is read as text; casting happens in 02_transform.

DROP TABLE IF EXISTS energy_raw;
DROP TABLE IF EXISTS energy_clean;
DROP TABLE IF EXISTS mart_energy;
DROP TABLE IF EXISTS cost_by_fuel;
DROP TABLE IF EXISTS costliest_buildings;
DROP TABLE IF EXISTS cost_per_unit_by_fuel;
DROP TABLE IF EXISTS headline;

CREATE TABLE energy_raw (
  energy_type      VARCHAR,
  building_name    VARCHAR,
  hrm_building_id  VARCHAR,
  unit_of_measure  VARCHAR,
  consumption      VARCHAR,
  cost             VARCHAR
);

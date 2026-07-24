-- 01_load.sql
-- Question this step answers: what records are in each pinned GeoJSON snapshot?
-- ST_Read pulls both the attributes and the WGS84 geometry from each committed
-- snapshot into a raw table. The paths are relative to the project folder, so
-- run.py must be launched from here.
--
-- The ice-route snapshot's coordinates were rounded to six decimal places
-- (about 0.1 m) when the pull was saved, to keep the committed file compact; see
-- SOURCE.md. That rounding touches only the drawn geometry, never the
-- Shape__Length attribute the ice-route length golden is summed from, so the
-- result is unaffected.

CREATE TABLE street_raw AS
  SELECT *
  FROM ST_Read('data/raw/hrm_street-winter-maintenance-areas_2026-07-13.geojson');

CREATE TABLE sidewalk_raw AS
  SELECT *
  FROM ST_Read('data/raw/hrm_sidewalk-winter-maintenance-areas_2026-07-13.geojson');

CREATE TABLE ice_raw AS
  SELECT *
  FROM ST_Read('data/raw/hrm_ice-routes_2026-07-13.geojson');

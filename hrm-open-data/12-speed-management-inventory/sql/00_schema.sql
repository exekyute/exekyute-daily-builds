-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is the
-- raw shape of one speed display sign, one traffic control location, and one
-- neighbourhood speed-limit segment?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the two raw landing tables. The two point layers land together in
-- points_raw with a source_layer discriminator; the coded device value lands as
-- VARCHAR (SIGNTYPE is already a short string code, CONTROL_TYPE is an integer
-- cast to text) so a single decode step in 02_transform maps every code to its
-- label. install_year lands as VARCHAR so the type cast happens in one place.
-- The polyline layer lands in lines_raw with just the posted speed and the
-- segment length in metres, the only two source fields the summary needs.
-- The spatial extension is loaded here because 01_load reads the polyline
-- GeoJSON with ST_Read.

INSTALL spatial;
LOAD spatial;

DROP TABLE IF EXISTS points_raw;
DROP TABLE IF EXISTS lines_raw;
DROP TABLE IF EXISTS points_clean;
DROP TABLE IF EXISTS lines_clean;
DROP TABLE IF EXISTS mart_points;
DROP TABLE IF EXISTS counts_by_device;
DROP TABLE IF EXISTS speed_by_limit;
DROP TABLE IF EXISTS headline;

CREATE TABLE points_raw (
  source_layer VARCHAR,
  device_code  VARCHAR,
  install_year VARCHAR,
  location     VARCHAR,
  lat          DOUBLE,
  lon          DOUBLE
);

CREATE TABLE lines_raw (
  speed_limit INTEGER,
  len_m       DOUBLE
);

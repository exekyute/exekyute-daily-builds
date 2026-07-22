-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is
-- the raw shape of the three transit layers?
-- Reset every table so a re-run starts from a clean, repeatable state, load the
-- spatial extension (the park and ride layer ships as polygons and needs
-- ST_Centroid to give the map a single point per lot), then declare the raw
-- landing tables. The bus-stop and shelter text fields land as VARCHAR so every
-- cast happens in one place, 02_transform. The point coordinates land as DOUBLE:
-- they are numeric geometry read from the GeoJSON, not text. Park and ride
-- capacity lands as INTEGER because ST_Read already types it from the layer.

INSTALL spatial;
LOAD spatial;

DROP TABLE IF EXISTS stops_raw;
DROP TABLE IF EXISTS shelters_raw;
DROP TABLE IF EXISTS parkride_raw;
DROP TABLE IF EXISTS stops_clean;
DROP TABLE IF EXISTS shelters_clean;
DROP TABLE IF EXISTS parkride_clean;
DROP TABLE IF EXISTS mart_stops;
DROP TABLE IF EXISTS mart_parkride;
DROP TABLE IF EXISTS access_summary;
DROP TABLE IF EXISTS headline;

CREATE TABLE stops_raw (
  busstopid  VARCHAR,
  stopnumber VARCHAR,
  location   VARCHAR,
  accessible VARCHAR,
  busstatus  VARCHAR,
  lon        DOUBLE,
  lat        DOUBLE
);

CREATE TABLE shelters_raw (
  shelterid VARCHAR,
  busstopid VARCHAR,
  location  VARCHAR
);

CREATE TABLE parkride_raw (
  pnrid    VARCHAR,
  name     VARCHAR,
  address  VARCHAR,
  capacity INTEGER,
  routes   VARCHAR,
  lon      DOUBLE,
  lat      DOUBLE
);

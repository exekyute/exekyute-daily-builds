-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is
-- the raw shape of one EV charging station record?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. The text fields land as VARCHAR. The install
-- year and quantity land as VARCHAR too, so every type cast happens in one
-- place, 02_transform. POWER lands as DOUBLE (a numeric power rating in kW).
-- The point coordinates land as DOUBLE: they are numeric geometry read from the
-- GeoJSON point, not text.

DROP TABLE IF EXISTS ev_raw;
DROP TABLE IF EXISTS ev_clean;
DROP TABLE IF EXISTS chargers_by_year;
DROP TABLE IF EXISTS counts_by_chartype;
DROP TABLE IF EXISTS counts_by_connectype;
DROP TABLE IF EXISTS headline;

CREATE TABLE ev_raw (
  objectid   BIGINT,
  evcsid     VARCHAR,
  owner      VARCHAR,
  chartype   VARCHAR,
  connectype VARCHAR,
  power      DOUBLE,
  powerunit  VARCHAR,
  location   VARCHAR,
  access     VARCHAR,
  instyr     VARCHAR,
  quantity   VARCHAR,
  assetstat  VARCHAR,
  lon        DOUBLE,
  lat        DOUBLE
);

-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is
-- the raw shape of the source file?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. Every raw column is VARCHAR because the Hub
-- CSV export delivers each field as text; parsing and casting happen in
-- 02_transform. Only the columns the build actually uses are declared here.

DROP TABLE IF EXISTS collisions_raw;
DROP TABLE IF EXISTS collisions_clean;
DROP TABLE IF EXISTS collisions_by_year;
DROP TABLE IF EXISTS collisions_month_hour;
DROP TABLE IF EXISTS headline;

CREATE TABLE collisions_raw (
  collision_id             VARCHAR,
  accident_datetime        VARCHAR,
  lat                      VARCHAR,
  lon                      VARCHAR,
  road_location_1          VARCHAR,
  road_location_2          VARCHAR,
  road_configuration       VARCHAR,
  collision_configuration  VARCHAR,
  non_fatal_injury         VARCHAR,
  fatal_injury             VARCHAR,
  pedestrian_collisions    VARCHAR,
  bicycle_collisions       VARCHAR,
  aggressive_driving       VARCHAR,
  distracted_driving       VARCHAR,
  impaired_driving         VARCHAR,
  intersection_related     VARCHAR,
  light_condition          VARCHAR,
  weather_condition        VARCHAR
);

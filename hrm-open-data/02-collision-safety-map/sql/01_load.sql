-- 01_load.sql
-- Question this step answers: what rows are in the pinned snapshot?
-- Read the committed snapshot into the raw table. The Hub CSV export carries
-- friendly, space-separated column headers, so each source header is quoted and
-- aliased to the clean raw column name. all_varchar = true turns off type
-- auto-detection: every field lands as text and 02_transform does the casting,
-- so the load can never drift on a re-run. The path is relative to the project
-- folder, so run.py must be launched from here.

INSERT INTO collisions_raw
SELECT
  "COLLISION_SK"              AS collision_id,
  "Accident Date and Time"    AS accident_datetime,
  "Latitude WGS84"            AS lat,
  "Longitude WGS84"           AS lon,
  "Road Location"             AS road_location_1,
  "Intersecting Road Location" AS road_location_2,
  "Road Configuration"        AS road_configuration,
  "Collision Configuration"   AS collision_configuration,
  "Non Fatal Injury"          AS non_fatal_injury,
  "Fatal Injury"              AS fatal_injury,
  "Pedestrian Collision"      AS pedestrian_collisions,
  "Bicycle Collision"         AS bicycle_collisions,
  "Aggressive Driving"        AS aggressive_driving,
  "Distracted Driving"        AS distracted_driving,
  "Impaired Driving"          AS impaired_driving,
  "Intersection Collision"    AS intersection_related,
  "Light Condition"           AS light_condition,
  "Weather Condition"         AS weather_condition
FROM read_csv(
  'data/raw/hrm_traffic-collisions_2026-07-09.csv',
  header      = true,
  all_varchar = true
);

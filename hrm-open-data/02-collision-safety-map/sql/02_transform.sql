-- 02_transform.sql
-- Question this step answers: what does one clean, typed row per collision
-- look like?
-- Parse the local accident timestamp, cast the coordinates to doubles, turn each
-- Y/N or Yes factor field into a clean 0/1 integer, and derive the calendar
-- parts the two dashboards and the golden both bind to. Rows with no parseable
-- timestamp or no coordinates are dropped here, so every downstream count works
-- on a complete, typed record.
--
-- The snapshot renders "Accident Date and Time" in local Halifax wall-clock
-- time (the source service stores it as an epoch, the CSV export localizes it),
-- so the derived hour and weekday read as the time a Haligonian experienced,
-- with no timezone arithmetic. The format is M/D/YYYY h:mm:ss AM/PM.

CREATE TABLE collisions_clean AS
WITH parsed AS (
  SELECT
    CAST(trim(collision_id) AS BIGINT) AS collision_id,
    strptime(trim(accident_datetime), '%-m/%-d/%Y %-I:%M:%S %p') AS ldt,
    CAST(trim(lat) AS DOUBLE) AS lat,
    CAST(trim(lon) AS DOUBLE) AS lon,
    trim(road_location_1)         AS road_location_1,
    trim(road_location_2)         AS road_location_2,
    trim(collision_configuration) AS collision_configuration,
    trim(light_condition)         AS light_condition,
    trim(weather_condition)       AS weather_condition,
    CASE WHEN upper(trim(pedestrian_collisions)) = 'Y' THEN 1 ELSE 0 END AS PEDESTRIAN_COLLISIONS,
    CASE WHEN upper(trim(bicycle_collisions))    = 'Y' THEN 1 ELSE 0 END AS BICYCLE_COLLISIONS,
    CASE WHEN upper(trim(impaired_driving))      = 'Y' THEN 1 ELSE 0 END AS IMPAIRED_DRIVING,
    CASE WHEN upper(trim(distracted_driving))    = 'Y' THEN 1 ELSE 0 END AS DISTRACTED_DRIVING,
    CASE WHEN upper(trim(aggressive_driving))    = 'Y' THEN 1 ELSE 0 END AS AGRESSIVE_DRIVING,
    CASE WHEN upper(trim(intersection_related))  = 'Y' THEN 1 ELSE 0 END AS INTERSECTION_RELATED,
    CASE WHEN fatal_injury     IS NOT NULL AND upper(trim(fatal_injury))     IN ('YES', 'Y') THEN 1 ELSE 0 END AS FATAL_INJURY,
    CASE WHEN non_fatal_injury IS NOT NULL AND upper(trim(non_fatal_injury)) IN ('YES', 'Y') THEN 1 ELSE 0 END AS NON_FATAL_INJURY
  FROM collisions_raw
  WHERE accident_datetime IS NOT NULL AND trim(accident_datetime) <> ''
    AND lat IS NOT NULL AND trim(lat) <> ''
    AND lon IS NOT NULL AND trim(lon) <> ''
)
SELECT
  collision_id,
  CAST(ldt AS DATE) AS accident_date,
  CAST(year(ldt)   AS INTEGER) AS year,
  CAST(month(ldt)  AS INTEGER) AS month,
  CAST(hour(ldt)   AS INTEGER) AS hour,
  CAST(isodow(ldt) AS INTEGER) AS weekday,   -- 1 = Monday ... 7 = Sunday
  lat,
  lon,
  road_location_1,
  road_location_2,
  collision_configuration,
  light_condition,
  weather_condition,
  PEDESTRIAN_COLLISIONS,
  BICYCLE_COLLISIONS,
  IMPAIRED_DRIVING,
  DISTRACTED_DRIVING,
  AGRESSIVE_DRIVING,
  INTERSECTION_RELATED,
  FATAL_INJURY,
  NON_FATAL_INJURY
FROM parsed
WHERE ldt IS NOT NULL;

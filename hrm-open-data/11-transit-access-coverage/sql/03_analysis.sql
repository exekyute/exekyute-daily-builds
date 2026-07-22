-- 03_analysis.sql
-- The analytical core. Two marts, one summary, one headline. The grain of the
-- stops mart is one row per bus stop; the park and ride mart is one row per lot.

-- mart_stops: one row per bus stop, with a shelter flag joined on. has_shelter
-- is 1 when at least one shelter record links to this stop by BUSSTOPID. A stop
-- can carry more than one shelter (both directions of a street), so the flag is
-- an EXISTS test, not a count, which keeps it a clean 0/1 per stop. Shelter
-- records with a blank or non-matching BUSSTOPID (a handful reference a stop id
-- not in the current stop layer) set no flag on any stop.
CREATE TABLE mart_stops AS
SELECT
  s.busstopid,
  s.stopnumber,
  s.location,
  s.accessible,
  s.status,
  CASE WHEN EXISTS (
    SELECT 1 FROM shelters_clean sh
    WHERE sh.busstopid <> '' AND sh.busstopid = s.busstopid
  ) THEN 1 ELSE 0 END AS has_shelter,
  s.lat,
  s.lon
FROM stops_clean s;

-- mart_parkride: one row per park and ride lot, with the polygon reduced to its
-- centroid point in 01_load. capacity is the posted parking capacity; routes is
-- the free-text list of routes the lot serves.
CREATE TABLE mart_parkride AS
SELECT
  name,
  capacity,
  routes,
  lat,
  lon
FROM parkride_clean;

-- access_summary: the golden coverage figures in one row. total_shelters counts
-- every shelter record (some sit at the same stop and some reference a stop id
-- outside the layer), which is why it exceeds stops_with_shelter. The two shares
-- are rounded to one decimal so the row is byte-stable.
CREATE TABLE access_summary AS
SELECT
  (SELECT count(*)          FROM mart_stops)                     AS total_stops,
  (SELECT sum(accessible)   FROM mart_stops)                     AS accessible_stops,
  round(100.0 * (SELECT sum(accessible)  FROM mart_stops)
              / (SELECT count(*)         FROM mart_stops), 1)    AS accessible_share_pct,
  (SELECT count(*)          FROM shelters_clean)                 AS total_shelters,
  (SELECT sum(has_shelter)  FROM mart_stops)                     AS stops_with_shelter,
  round(100.0 * (SELECT sum(has_shelter) FROM mart_stops)
              / (SELECT count(*)         FROM mart_stops), 1)    AS shelter_coverage_pct,
  (SELECT count(*)          FROM mart_parkride)                  AS parkride_lots,
  (SELECT sum(capacity)     FROM mart_parkride)                  AS parkride_capacity;

-- headline: two ready-to-print lines run.py echoes. Every figure is read from
-- access_summary, not hardcoded.
CREATE TABLE headline AS
WITH s AS (SELECT * FROM access_summary)
SELECT 1 AS ord,
  'HRM lists ' || (SELECT total_stops FROM s) || ' bus stops, '
    || (SELECT stops_with_shelter FROM s) || ' of them with a shelter '
    || '(shelter coverage ' || (SELECT shelter_coverage_pct FROM s) || ' percent).' AS line
UNION ALL
SELECT 2 AS ord,
  (SELECT accessible_stops FROM s) || ' stops are accessible ('
    || (SELECT accessible_share_pct FROM s) || ' percent), and '
    || (SELECT parkride_lots FROM s) || ' park and ride lots add '
    || (SELECT parkride_capacity FROM s) || ' parking spaces.' AS line
ORDER BY ord;

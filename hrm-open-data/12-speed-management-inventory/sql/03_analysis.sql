-- 03_analysis.sql
-- Three tables plus a headline. The point grain is one row per device; the line
-- grain is one row per road segment. None of these carry a community column, so
-- coverage is summarised by device type for the points and by posted speed for the
-- segments, not by community.

-- mart_points: the per-device map table, one row per point device (780 rows). This
-- is the frozen mart both the SQL golden and the Tableau point layer read: every
-- device with its source layer, decoded device type, install year, location, and
-- WGS84 coordinate.
CREATE TABLE mart_points AS
SELECT
  source_layer,
  device_type,
  install_year,
  location,
  lat,
  lon
FROM points_clean;

-- counts_by_device: how many devices carry each device type, within each source
-- layer. The signs are all one type (Speed Display Sign, 73); the control locations
-- split across eight traffic-control types. This is the coverage-by-device-type
-- summary the map legend reads.
CREATE TABLE counts_by_device AS
SELECT
  source_layer,
  device_type,
  COUNT(*) AS devices
FROM mart_points
GROUP BY source_layer, device_type;

-- speed_by_limit: how many neighbourhood road segments carry each posted speed
-- limit, and how many kilometres that is. total_km is the published segment length
-- Shape__Length (metres) summed and divided by 1000, rounded to two decimals. The
-- final row, with a blank speed_limit, is the 156 segments the source leaves with
-- no posted limit.
CREATE TABLE speed_by_limit AS
SELECT
  speed_limit,
  COUNT(*)                       AS segments,
  round(SUM(len_m) / 1000.0, 2)  AS total_km
FROM lines_clean
GROUP BY speed_limit;

-- headline: the ready-to-print lines run.py echoes. Line one gives the total point
-- devices mapped and the sign / control split. Line two reads the control-type mix
-- off counts_by_device. Line three gives the total posted neighbourhood road length
-- and the reduced-speed subset: segments and kilometres posted below the 50 km/h
-- Nova Scotia urban default. The reduced-speed figures come straight from the raw
-- lengths (speed_limit < 50 excludes the unposted NULL segments), not from the
-- rounded per-speed rows, so they do not drift. Every figure is read from the
-- tables above, not hardcoded.
CREATE TABLE headline AS
WITH dev AS (
  SELECT
    SUM(devices) AS total_devices,
    SUM(devices) FILTER (WHERE source_layer = 'Speed Display Sign')       AS signs,
    SUM(devices) FILTER (WHERE source_layer = 'Traffic Control Location') AS controls
  FROM counts_by_device
),
ctrl_mix AS (
  SELECT string_agg(devices || ' ' || device_type, ', ' ORDER BY devices DESC, device_type) AS s
  FROM counts_by_device
  WHERE source_layer = 'Traffic Control Location'
),
seg AS (
  SELECT
    COUNT(*)                                                    AS total_segments,
    round(SUM(len_m) / 1000.0, 2)                               AS total_km,
    COUNT(*) FILTER (WHERE speed_limit < 50)                    AS reduced_segments,
    round(SUM(len_m) FILTER (WHERE speed_limit < 50) / 1000.0, 2) AS reduced_km
  FROM lines_clean
)
SELECT 1 AS ord,
  'The inventory maps ' || (SELECT total_devices FROM dev)
    || ' point devices across Halifax: ' || (SELECT signs FROM dev)
    || ' speed display signs and ' || (SELECT controls FROM dev)
    || ' traffic control locations.' AS line
UNION ALL
SELECT 2 AS ord,
  'Traffic control locations by type: ' || (SELECT s FROM ctrl_mix) || '.' AS line
UNION ALL
SELECT 3 AS ord,
  'Neighbourhood streets carry ' || printf('%.2f', (SELECT total_km FROM seg))
    || ' km of posted speed limits across ' || (SELECT total_segments FROM seg)
    || ' segments, of which ' || printf('%.2f', (SELECT reduced_km FROM seg))
    || ' km on ' || (SELECT reduced_segments FROM seg)
    || ' segments are posted below the 50 km/h default.' AS line
ORDER BY ord;

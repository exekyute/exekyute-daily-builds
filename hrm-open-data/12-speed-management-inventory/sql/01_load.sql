-- 01_load.sql
-- Question this step answers: what records are in the three pinned snapshots?
-- The two point layers were pulled with outSR=4326, so each feature carries a
-- WGS84 point in geometry; DuckDB list indexing is 1-based, so coordinates[1] is
-- longitude and coordinates[2] is latitude. read_json unnests the FeatureCollection
-- and reads each property straight into points_raw. The speed display signs carry
-- their device kind in SIGNTYPE (a string code); the traffic control locations
-- carry it in CONTROL_TYPE (an integer code) which is cast to VARCHAR so both land
-- in one column and get decoded together in 02_transform.
-- The polyline layer is read with ST_Read from the spatial extension, which exposes
-- each feature's attributes as columns; only the posted SPEED and the segment
-- length Shape__Length (in metres) are kept. The summary sums that published length,
-- so the raw geometry is not needed here.
-- Every path is relative to the project folder, so run.py must be launched here.

INSERT INTO points_raw
SELECT
  'Speed Display Sign'                     AS source_layer,
  feature.properties.SIGNTYPE::VARCHAR     AS device_code,
  feature.properties.INSTYR::VARCHAR        AS install_year,
  feature.properties.LOCATION::VARCHAR      AS location,
  feature.geometry.coordinates[2]::DOUBLE   AS lat,
  feature.geometry.coordinates[1]::DOUBLE   AS lon
FROM (
  SELECT unnest(features) AS feature
  FROM read_json('data/raw/hrm_speed-display-signs_2026-07-13.geojson')
);

INSERT INTO points_raw
SELECT
  'Traffic Control Location'                AS source_layer,
  feature.properties.CONTROL_TYPE::VARCHAR  AS device_code,
  feature.properties.INSTYR::VARCHAR         AS install_year,
  feature.properties.LOCATION::VARCHAR       AS location,
  feature.geometry.coordinates[2]::DOUBLE    AS lat,
  feature.geometry.coordinates[1]::DOUBLE    AS lon
FROM (
  SELECT unnest(features) AS feature
  FROM read_json('data/raw/hrm_traffic-control-locations_2026-07-13.geojson')
);

INSERT INTO lines_raw
SELECT
  SPEED::INTEGER          AS speed_limit,
  "Shape__Length"::DOUBLE AS len_m
FROM ST_Read('data/raw/hrm_neighbourhood-speed-limit_2026-07-13.geojson');

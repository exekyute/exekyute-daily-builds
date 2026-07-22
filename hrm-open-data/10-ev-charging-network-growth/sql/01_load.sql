-- 01_load.sql
-- Question this step answers: what records are in the pinned GeoJSON snapshot?
-- Read the committed GeoJSON straight into the raw table. Each feature carries
-- the station attributes in properties and a WGS84 point in geometry. The point
-- coordinates are [longitude, latitude]; DuckDB list indexing is 1-based, so
-- coordinates[1] is longitude and coordinates[2] is latitude. The snapshot was
-- pulled with outSR=4326 so the geometry is degrees, not a projected grid.
-- See SOURCE.md. The path is relative to the project folder, so run.py must be
-- launched here.

INSERT INTO ev_raw
SELECT
  feature.properties.OBJECTID::BIGINT     AS objectid,
  feature.properties.EVCSID::VARCHAR       AS evcsid,
  feature.properties.OWNER::VARCHAR         AS owner,
  feature.properties.CHARTYPE::VARCHAR      AS chartype,
  feature.properties.CONNECTYPE::VARCHAR    AS connectype,
  feature.properties.POWER::DOUBLE          AS power,
  feature.properties.POWERUNIT::VARCHAR     AS powerunit,
  feature.properties.LOCATION::VARCHAR      AS location,
  feature.properties.EVACCESS::VARCHAR      AS access,
  feature.properties.INSTYR::VARCHAR        AS instyr,
  feature.properties.QUANTITY::VARCHAR      AS quantity,
  feature.properties.ASSETSTAT::VARCHAR     AS assetstat,
  feature.geometry.coordinates[1]::DOUBLE   AS lon,
  feature.geometry.coordinates[2]::DOUBLE   AS lat
FROM (
  SELECT unnest(features) AS feature
  FROM read_json('data/raw/hrm_ev-charging-station_2026-07-13.geojson')
);

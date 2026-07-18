-- 01_load.sql
-- Question this step answers: what records are in the pinned GeoJSON snapshot?
-- Read the committed GeoJSON straight into the raw table. Each feature carries
-- the project attributes in properties and a WGS84 point in geometry. The point
-- coordinates are [longitude, latitude]; DuckDB list indexing is 1-based, so
-- coordinates[1] is longitude and coordinates[2] is latitude. The source
-- NORTHING and EASTING columns are projected grid values and are deliberately
-- not read; the lat and long come from the GeoJSON point instead. See SOURCE.md.
-- The path is relative to the project folder, so run.py must be launched here.

INSERT INTO cap_raw
SELECT
  feature.properties.OBJECTID::BIGINT     AS objectid,
  feature.properties.PROJ_NO::VARCHAR     AS proj_no,
  feature.properties.PROJ_NAME::VARCHAR   AS proj_name,
  feature.properties.LOC_ID::VARCHAR      AS loc_id,
  feature.properties.LOC_DESC::VARCHAR    AS loc_desc,
  feature.properties.WORK_DESC::VARCHAR   AS work_desc,
  feature.properties.CATEGORY::VARCHAR    AS category,
  feature.properties.ASSET_TYPE::VARCHAR  AS asset_type,
  feature.properties.YEAR::VARCHAR        AS year,
  feature.geometry.coordinates[1]::DOUBLE AS lon,
  feature.geometry.coordinates[2]::DOUBLE AS lat
FROM (
  SELECT unnest(features) AS feature
  FROM read_json('data/raw/hrm_capital-projects_2026-07-09.geojson')
);

-- 01_load.sql
-- Question this step answers: what records are in the two pinned GeoJSON
-- snapshots?
-- Two layers are read straight from the committed GeoJSON with the spatial
-- reader ST_Read, which returns each feature's attributes as columns plus the
-- polygon as a geom GEOMETRY column in WGS84 (EPSG:4326).
--   * Zoning Boundaries: 11,076 land-use polygons. ZONE is the raw zone code
--     (some null) and DESCRIPTION the plain-language label. The service also
--     carries a Shape__Area column, but it is stored in the service's Web
--     Mercator projection (EPSG:3857), which inflates area by roughly three
--     times at Halifax's latitude and would misstate absolute areas. It is
--     therefore not read; area is computed as true geodesic ground area from the
--     WGS84 geometry in 02_transform. See SOURCE.md.
--   * Community Boundaries (General Service Areas): 200 community polygons.
--     GSA_NAME is the community name. Zoning carries no community column, so
--     this layer supplies the geometry the "by community" rollup needs.
-- The paths are relative to the project folder, so run.py must be launched here.

CREATE TABLE zoning_raw AS
SELECT
  OBJECTID,
  ZONE,
  DESCRIPTION,
  geom
FROM ST_Read('data/raw/hrm_zoning-boundaries_2026-07-13.geojson');

CREATE TABLE gsa_raw AS
SELECT
  GSA_NAME,
  MUN_CODE,
  geom
FROM ST_Read('data/raw/hrm_community-boundaries_2026-07-13.geojson');

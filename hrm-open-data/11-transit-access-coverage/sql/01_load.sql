-- 01_load.sql
-- Question this step answers: what records are in the three pinned snapshots?
-- Read the committed GeoJSON files straight into the raw tables. The bus-stop
-- and shelter layers are points: each feature carries its attributes in
-- properties and a WGS84 point in geometry. The coordinates are
-- [longitude, latitude]; DuckDB list indexing is 1-based, so coordinates[1] is
-- longitude and coordinates[2] is latitude. Both snapshots were pulled with
-- outSR=4326 so the geometry is degrees, not a projected grid. The park and ride
-- layer is polygons, so it is read with ST_Read and reduced to one interior
-- point per lot with ST_Centroid (ST_X is longitude, ST_Y is latitude). The
-- paths are relative to the project folder, so run.py must be launched here.

INSERT INTO stops_raw
SELECT
  f.properties.BUSSTOPID::VARCHAR   AS busstopid,
  f.properties.STOPNUMBER::VARCHAR  AS stopnumber,
  f.properties.LOCATION::VARCHAR    AS location,
  f.properties.ACCESSIBLE::VARCHAR  AS accessible,
  f.properties.BUSSTATUS::VARCHAR   AS busstatus,
  f.geometry.coordinates[1]::DOUBLE AS lon,
  f.geometry.coordinates[2]::DOUBLE AS lat
FROM (
  SELECT unnest(features) AS f
  FROM read_json('data/raw/hrm_bus-stops_2026-07-13.geojson')
);

INSERT INTO shelters_raw
SELECT
  f.properties.SHELTERID::VARCHAR AS shelterid,
  f.properties.BUSSTOPID::VARCHAR AS busstopid,
  f.properties.LOCATION::VARCHAR  AS location
FROM (
  SELECT unnest(features) AS f
  FROM read_json('data/raw/hrm_transit-shelters_2026-07-13.geojson')
);

INSERT INTO parkride_raw
SELECT
  PNRID::VARCHAR              AS pnrid,
  PNR_NAME::VARCHAR           AS name,
  ADDRESS::VARCHAR            AS address,
  PARKING_CAPACITY::INTEGER   AS capacity,
  ROUTES_SERVICED::VARCHAR    AS routes,
  ST_X(ST_Centroid(geom))::DOUBLE AS lon,
  ST_Y(ST_Centroid(geom))::DOUBLE AS lat
FROM ST_Read('data/raw/hrm_park-ride_2026-07-13.geojson');

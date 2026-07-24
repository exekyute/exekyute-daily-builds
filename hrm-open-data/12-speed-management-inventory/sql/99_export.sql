-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files?
-- Write the per-device mart and the two summary tables to out/. Every query ends
-- in an ORDER BY so the row order is fixed and the output is byte-for-byte
-- reproducible against expected/. The mart order reaches lat and lon (six-decimal
-- coordinates) so any two devices that share every earlier field still emit
-- identical lines, keeping the file stable. speed_by_limit orders by the posted
-- limit with the unposted (NULL) segments last.

COPY (
  SELECT source_layer, device_type, install_year, location, lat, lon
  FROM mart_points
  ORDER BY source_layer, device_type, install_year NULLS LAST, location, lat, lon
) TO 'out/mart_points.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT source_layer, device_type, devices
  FROM counts_by_device
  ORDER BY source_layer, devices DESC, device_type
) TO 'out/counts_by_device.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT speed_limit, segments, total_km
  FROM speed_by_limit
  ORDER BY speed_limit NULLS LAST
) TO 'out/speed_by_limit.csv' (HEADER, DELIMITER ',');

-- The same 780 devices written a second time as a point GeoJSON. The CSV above is
-- the readable mart and the golden; this file is the spatial twin of it, carrying an
-- ST_Point built from the same lon and lat. Tableau layers a spatial field over
-- another spatial field, so publishing the devices as real geometry (rather than two
-- number columns) is what lets the device layer and the speed_limits line layer sit
-- on one map. ST_Point takes x then y, so lon comes first. Same ORDER BY as the CSV,
-- so the feature order matches the mart row for row.
-- device_id is a stable 1 to 780 key numbered by the same ORDER BY the CSV mart
-- uses, so feature 1 here is row 1 there. It exists because Tableau aggregates a
-- spatial layer with COLLECT(Geometry) and needs a unique field on Detail to split
-- the collection back into one mark per device; without it the 780 points collapse
-- into a couple of dozen grouped marks drawn at their centres.
COPY (
  SELECT
    ST_Point(lon, lat) AS geom,
    ROW_NUMBER() OVER (
      ORDER BY source_layer, device_type, install_year NULLS LAST, location, lat, lon
    ) AS device_id,
    source_layer,
    device_type,
    install_year,
    location
  FROM mart_points
  ORDER BY source_layer, device_type, install_year NULLS LAST, location, lat, lon
) TO 'out/speed_devices.geojson' WITH (FORMAT GDAL, DRIVER 'GeoJSON');

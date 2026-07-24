-- 99_export.sql
-- Question this step answers: what are the deterministic result file and the map
-- layers the single Tableau dashboard renders?
-- The tabular golden is written to out/ with a fixed row order, so it diffs
-- byte-for-byte against expected/. The three cleaned map layers are written to
-- bi/exports/ as GeoJSON at six-decimal coordinate precision (about 0.1 m), one
-- feature per polygon area and one dissolved multi-line feature per ice-route
-- priority. Tableau renders those files directly; the golden is not the geometry
-- but the summary computed from it.

-- The tabular golden.
COPY (
  SELECT section, category, feature_count, length_km, area_km2
  FROM coverage_summary
  ORDER BY section_ord, row_ord
) TO 'out/coverage_summary.csv' (HEADER, DELIMITER ',');

-- Map layer 1: street winter maintenance areas, coloured in Tableau by serve_by.
-- ST_Multi promotes every feature to MultiPolygon so the layer is one uniform
-- geometry type: Tableau aggregates a spatial layer with COLLECT and refuses a
-- mix of Polygon and MultiPolygon ("MixedGeometry ... not supported yet"). The
-- coordinate precision is 7, not 6: at 6 the GDAL writer degenerates one thin
-- polygon into a GeometryCollection, which is the same mixed-type problem.
COPY (
  SELECT area_id, serve_by, servarea, area_km2, ST_Multi(geom) AS geom
  FROM street_clean
  ORDER BY serve_by, servarea, area_id
) TO 'bi/exports/street_winter_areas.geojson'
  WITH (FORMAT GDAL, DRIVER 'GeoJSON', LAYER_CREATION_OPTIONS 'COORDINATE_PRECISION=7');

-- Map layer 2: sidewalk winter maintenance areas, a second polygon fill. Same
-- ST_Multi promotion to a uniform MultiPolygon type for Tableau.
COPY (
  SELECT area_id, machine, fcode, area_km2, ST_Multi(geom) AS geom
  FROM sidewalk_clean
  ORDER BY machine, area_id
) TO 'bi/exports/sidewalk_winter_areas.geojson'
  WITH (FORMAT GDAL, DRIVER 'GeoJSON', LAYER_CREATION_OPTIONS 'COORDINATE_PRECISION=7');

-- Map layer 3: ice routes dissolved to one feature per priority, drawn as lines
-- coloured by priority. Each feature carries its segment count and its length in
-- km, so the same length that sits in the golden rides on the map feature.
COPY (
  SELECT priority, segment_count, length_km, geom
  FROM ice_by_priority
  ORDER BY CASE priority WHEN '1' THEN 1 WHEN '2' THEN 2 ELSE 3 END
) TO 'bi/exports/ice_routes_by_priority.geojson'
  WITH (FORMAT GDAL, DRIVER 'GeoJSON', LAYER_CREATION_OPTIONS 'COORDINATE_PRECISION=6');

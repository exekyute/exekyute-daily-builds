-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files?
-- Write the three golden tables to out/, each ending in an ORDER BY so the row
-- order is fixed and the output is byte-for-byte reproducible against expected/.
-- Also write the tagged zoning polygons straight to bi/exports as GeoJSON for
-- the Tableau choropleth: one feature per polygon carrying its zone_class,
-- community, raw zone code, description, and area, with the geometry at six
-- decimal places. run.py copies out/mart_landuse.csv into bi/exports for the
-- two BI tools; the geometry export is written here because it needs the spatial
-- engine.

COPY (
  SELECT community, zone_class, polygons, area, area_share
  FROM mart_landuse
  ORDER BY community, zone_class
) TO 'out/mart_landuse.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT community_mix_rank, community, classes, total_area,
         dominant_class, largest_class_share, mix_index
  FROM community_mix_ranking
  ORDER BY community_mix_rank, community
) TO 'out/community_mix_ranking.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT zone_class, polygons, area, area_share
  FROM class_area_overall
  ORDER BY area_share DESC, zone_class
) TO 'out/class_area_overall.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT zone_class, community, ZONE AS zone, description,
         CAST(ROUND(area_m2 / 1000000.0, 4) AS DECIMAL(14,4)) AS area_km2,
         geom
  FROM zoning_tagged
  ORDER BY OBJECTID
) TO 'bi/exports/zoning_tagged.geojson'
  WITH (FORMAT GDAL, DRIVER 'GeoJSON', LAYER_CREATION_OPTIONS 'COORDINATE_PRECISION=6');

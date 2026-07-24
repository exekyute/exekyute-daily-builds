-- 03_analysis.sql
-- Question this step answers: how is winter maintenance responsibility carved up
-- across street providers, sidewalk zones, and ice-route priorities?
-- Three groupings, one per layer, are stacked into a single long summary table:
-- street polygons counted by servicing body, sidewalk polygons counted by zone,
-- and ice-route length rolled up by priority. Each section carries its own
-- deterministic row order (row_ord), so a single ORDER BY over section then
-- row_ord in the export fixes the whole file.

-- Dissolve the 18,736 ice-route segments to one feature per priority. The count
-- and length come from the attribute rows (agg): segment_count is the number of
-- route records and length_km is the plain sum of the source Shape__Length in
-- metres, carried to km. The drawn geometry (geo) is built separately by
-- exploding every segment to its component LineStrings with ST_Dump, then
-- bundling them with ST_Collect into one MultiLineString per priority. Exploding
-- first guarantees a uniform MultiLineString (a raw mix of LineString and
-- MultiLineString would otherwise collect to a GeometryCollection) and drops the
-- ten records whose geometry is null; those records still count toward the
-- attribute totals, since they are real routes the map simply cannot draw.
CREATE TABLE ice_by_priority AS
WITH agg AS (
  SELECT
    priority,
    COUNT(*)                                         AS segment_count,
    CAST(SUM(shape_len_m) / 1000.0 AS DECIMAL(12,2)) AS length_km
  FROM ice_clean
  GROUP BY priority
),
geo AS (
  SELECT priority, ST_Multi(ST_Collect(array_agg(line_geom))) AS geom
  FROM (
    SELECT priority, UNNEST(ST_Dump(geom)).geom AS line_geom
    FROM ice_clean
  )
  GROUP BY priority
)
SELECT a.priority, a.segment_count, a.length_km, g.geom
FROM agg a
JOIN geo g USING (priority);

-- The stacked summary. Polygon sections carry a group area in square kilometres
-- and no length; the ice section carries length in km and no area.
CREATE TABLE coverage_summary AS
WITH street_g AS (
  SELECT
    'street_by_serve_by'                                        AS section,
    serve_by                                                    AS category,
    COUNT(*)                                                    AS feature_count,
    CAST(NULL AS DECIMAL(12,2))                                 AS length_km,
    CAST(SUM(ST_Area_Spheroid(geom)) / 1000000.0 AS DECIMAL(14,4)) AS area_km2
  FROM street_clean
  GROUP BY serve_by
),
sidewalk_g AS (
  SELECT
    'sidewalk_by_machine'                                       AS section,
    machine                                                     AS category,
    COUNT(*)                                                    AS feature_count,
    CAST(NULL AS DECIMAL(12,2))                                 AS length_km,
    CAST(SUM(ST_Area_Spheroid(geom)) / 1000000.0 AS DECIMAL(14,4)) AS area_km2
  FROM sidewalk_clean
  GROUP BY machine
),
ice_g AS (
  SELECT
    'ice_by_priority'          AS section,
    priority                   AS category,
    segment_count              AS feature_count,
    length_km                  AS length_km,
    CAST(NULL AS DECIMAL(14,4)) AS area_km2
  FROM ice_by_priority
),
street_o AS (
  SELECT 1 AS section_ord,
         ROW_NUMBER() OVER (ORDER BY feature_count DESC, category ASC) AS row_ord,
         section, category, feature_count, length_km, area_km2
  FROM street_g
),
sidewalk_o AS (
  SELECT 2 AS section_ord,
         ROW_NUMBER() OVER (ORDER BY area_km2 DESC, category ASC) AS row_ord,
         section, category, feature_count, length_km, area_km2
  FROM sidewalk_g
),
ice_o AS (
  SELECT 3 AS section_ord,
         ROW_NUMBER() OVER (
           ORDER BY CASE category WHEN '1' THEN 1 WHEN '2' THEN 2 ELSE 3 END
         ) AS row_ord,
         section, category, feature_count, length_km, area_km2
  FROM ice_g
)
SELECT section_ord, row_ord, section, category, feature_count, length_km, area_km2
FROM street_o
UNION ALL SELECT section_ord, row_ord, section, category, feature_count, length_km, area_km2 FROM sidewalk_o
UNION ALL SELECT section_ord, row_ord, section, category, feature_count, length_km, area_km2 FROM ice_o;

-- Two ready-to-print headline lines. Line one is the top-priority ice-route
-- length and the wider priority split; line two is how the street network splits
-- across servicing bodies. run.py prints these; it computes nothing.
CREATE TABLE headline AS
WITH ice AS (
  SELECT
    MAX(CASE WHEN priority = '1' THEN length_km END)             AS p1_km,
    MAX(CASE WHEN priority = '1' THEN segment_count END)         AS p1_n,
    MAX(CASE WHEN priority = '2' THEN length_km END)             AS p2_km,
    MAX(CASE WHEN priority = '(unassigned)' THEN length_km END)  AS pu_km
  FROM ice_by_priority
),
street_split AS (
  SELECT string_agg(serve_by || ' ' || cnt, ', ' ORDER BY cnt DESC, serve_by) AS split,
         COUNT(*)  AS providers,
         SUM(cnt)  AS areas
  FROM (SELECT serve_by, COUNT(*) AS cnt FROM street_clean GROUP BY serve_by)
)
SELECT 1 AS ord,
       'Priority 1 ice routes total ' || (SELECT p1_km FROM ice) || ' km across '
         || (SELECT p1_n FROM ice) || ' segments; priority 2 add '
         || (SELECT p2_km FROM ice) || ' km, and '
         || (SELECT pu_km FROM ice) || ' km carry no numbered priority.' AS line
UNION ALL
SELECT 2 AS ord,
       'Street winter maintenance splits across ' || (SELECT providers FROM street_split)
         || ' servicing bodies over ' || (SELECT areas FROM street_split)
         || ' areas: ' || (SELECT split FROM street_split) || '.' AS line;

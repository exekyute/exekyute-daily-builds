-- 02_transform.sql
-- Question this step answers: what is the clean, typed shape of each layer, with
-- one deterministic measure per feature?
-- Each layer is cleaned into its own table that keeps the geometry for the map
-- exports and adds the one measure the summary needs. Text fields are
-- whitespace-normalized: every run of whitespace, including the non-breaking
-- space (chr 160), is folded to a single space and trimmed, so no code or label
-- carries a hidden line break. A plain trim() clears only leading and trailing
-- spaces, so the regex collapse is what actually removes embedded breaks.
--
-- Measures. Polygon layers carry area in square kilometres from
-- ST_Area_Spheroid, which measures true ground area on the WGS84 ellipsoid, so
-- the projection of the source layer does not distort it. Ice-route segments
-- carry the source Shape__Length field in metres. Shape__Length is the layer's
-- own stored length in its native Web Mercator projection (EPSG:3857); it is
-- summed as provided so the SQL golden and a sum of the same field in Tableau
-- agree to the metre. See SOURCE.md on how this length relates to true ground
-- distance.

-- Street winter maintenance areas: one polygon per operational area, tagged with
-- the body that services it (SERVE_BY) and a service-area label (SERVAREA).
-- area_id is the source OBJECTID kept as a unique per-area key: SERVAREA repeats
-- (all 11 federal areas share the label DND), so a unique id is needed to give
-- Tableau one mark and one honest area tooltip per area rather than one merged
-- mark per SERVAREA.
CREATE TABLE street_clean AS
SELECT
  OBJECTID::BIGINT                                          AS area_id,
  trim(regexp_replace(SERVE_BY, '[\s\x{00a0}]+', ' ', 'g')) AS serve_by,
  trim(regexp_replace(SERVAREA, '[\s\x{00a0}]+', ' ', 'g')) AS servarea,
  round(ST_Area_Spheroid(geom) / 1000000.0, 4)              AS area_km2,
  geom
FROM street_raw;

-- Sidewalk winter maintenance areas: one polygon per service zone, tagged with
-- the machine/zone description (MACHINE) and a service-area code (FCODE).
-- area_id is the source OBJECTID; MACHINE is already unique per area, but the id
-- keeps the split field consistent with the street layer.
CREATE TABLE sidewalk_clean AS
SELECT
  OBJECTID::BIGINT                                         AS area_id,
  trim(regexp_replace(MACHINE, '[\s\x{00a0}]+', ' ', 'g')) AS machine,
  trim(regexp_replace(FCODE, '[\s\x{00a0}]+', ' ', 'g'))   AS fcode,
  round(ST_Area_Spheroid(geom) / 1000000.0, 4)             AS area_km2,
  geom
FROM sidewalk_raw;

-- Ice routes: one polyline per road segment, tagged with a snow-clearing
-- priority. PRIORITY is '1', '2', or null; a null carries no numbered road
-- priority (these are off-street and sidewalk maintenance codes) and is labelled
-- (unassigned) so the group is explicit rather than dropped. shape_len_m is the
-- source Shape__Length in metres, kept per segment for the priority roll-up.
CREATE TABLE ice_clean AS
SELECT
  coalesce(
    trim(regexp_replace(PRIORITY, '[\s\x{00a0}]+', ' ', 'g')),
    '(unassigned)'
  )                       AS priority,
  "Shape__Length"::DOUBLE AS shape_len_m,
  geom
FROM ice_raw;

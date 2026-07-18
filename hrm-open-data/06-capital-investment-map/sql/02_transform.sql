-- 02_transform.sql
-- Question this step answers: what does one clean, typed project record look
-- like, and which normalized category does it fall under?
-- The source free-text fields carry stray line breaks, tabs, and non-breaking
-- spaces that would otherwise split a CSV row or leave a hidden character on a
-- key. The norm CTE folds every run of whitespace (space, tab, CR, LF, and the
-- non-breaking space) down to a single space and trims each text field once, so
-- a plain trim of spaces is no longer relied on. The final SELECT then casts the
-- budget year to an integer, rounds the coordinates to six decimals, maps the
-- inconsistent CATEGORY labels onto a stable category_norm (the raw category is
-- kept beside it), and turns a blank asset type into an honest (unspecified)
-- bucket. Rows missing a project number, year, or category are dropped as a
-- guard; the current snapshot loses none.

CREATE TABLE cap_clean AS
WITH norm AS (
  SELECT
    objectid,
    trim(regexp_replace(replace(coalesce(proj_no,    ''), chr(160), ' '), '\s+', ' ', 'g')) AS proj_no,
    trim(regexp_replace(replace(coalesce(proj_name,  ''), chr(160), ' '), '\s+', ' ', 'g')) AS proj_name,
    trim(regexp_replace(replace(coalesce(loc_desc,   ''), chr(160), ' '), '\s+', ' ', 'g')) AS loc_desc,
    trim(regexp_replace(replace(coalesce(work_desc,  ''), chr(160), ' '), '\s+', ' ', 'g')) AS work_desc,
    trim(regexp_replace(replace(coalesce(category,   ''), chr(160), ' '), '\s+', ' ', 'g')) AS category,
    trim(regexp_replace(replace(coalesce(asset_type, ''), chr(160), ' '), '\s+', ' ', 'g')) AS asset_type,
    trim(regexp_replace(replace(coalesce(year,       ''), chr(160), ' '), '\s+', ' ', 'g')) AS year,
    lat,
    lon
  FROM cap_raw
)
SELECT
  objectid,
  proj_no,
  proj_name,
  loc_desc,
  work_desc,
  category,
  CASE category
    WHEN 'Roads & Active Transportation' THEN 'Roads'
    WHEN 'Roads & Streets'               THEN 'Roads'
    WHEN 'Parks & Playgrounds'           THEN 'Parks & Playgrounds'
    WHEN 'Parks and Playgrounds'         THEN 'Parks & Playgrounds'
    WHEN 'Parks'                         THEN 'Parks & Playgrounds'
    WHEN 'Buildings'                     THEN 'Buildings'
    WHEN 'Buildings/Facilities'          THEN 'Buildings'
    WHEN 'Halifax Transit'               THEN 'Transit'
    WHEN 'Metro Transit'                 THEN 'Transit'
    WHEN 'Sidewalks'                     THEN 'Sidewalks'
    WHEN 'Sidewalks, Curbs & Gutters'    THEN 'Sidewalks'
    WHEN 'Equipment & Fleet'             THEN 'Equipment & Fleet'
    WHEN 'Equipment & Machinery'         THEN 'Equipment & Fleet'
    WHEN 'Vehicles'                      THEN 'Equipment & Fleet'
    WHEN 'Halifax Water (CWWF)'          THEN 'Halifax Water'
    ELSE category
  END AS category_norm,
  CASE WHEN asset_type = '' THEN '(unspecified)' ELSE asset_type END AS asset_type,
  CAST(year AS INTEGER) AS year,
  round(lat, 6) AS lat,
  round(lon, 6) AS lon
FROM norm
WHERE proj_no <> ''
  AND year <> ''
  AND category <> '';

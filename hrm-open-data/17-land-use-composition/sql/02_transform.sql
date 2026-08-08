-- 02_transform.sql
-- Question this step answers: which broad land-use class does each zoning
-- polygon fall under, and which community is it in?
-- Two things happen here, both deterministic.
--
-- 1. zone_class. The raw ZONE field carries 206 distinct codes (plus a null),
--    and the same code is reused across bylaws with different meanings (C-5 is
--    "Mixed Use" in one bylaw and "Harbour Related Industrial" in another), so
--    the DESCRIPTION text is the more reliable signal and drives the mapping,
--    with the ZONE code as a secondary and fallback signal. An ordered CASE
--    folds every polygon into one of eight broad classes plus Unspecified for a
--    null ZONE. Order matters: earlier branches win, so "Mixed Industrial" lands
--    in Industrial and "Mixed Resource" in Rural and Resource before the generic
--    Mixed Use test is reached. The full mapping and the folding decisions are
--    documented in spec.md. The raw ZONE and DESCRIPTION are kept beside the
--    derived class.
--
-- 2. community. Zoning carries no community column, so each polygon is assigned
--    to the General Service Area whose boundary contains the polygon's centroid
--    (ST_Within(ST_Centroid(zoning.geom), gsa.geom)). Centroid assignment is a
--    single deterministic point-in-polygon test per polygon, far lighter than
--    full area apportionment across boundaries, and every polygon lands in
--    exactly one community. A centroid that falls outside every community
--    boundary (7 polygons, on the coastal edge) is labelled Unassigned rather
--    than dropped, so no area goes missing. The QUALIFY guard keeps the result
--    one row per polygon even if two boundaries were ever to overlap.
--
-- The description is whitespace-normalized first (stray tabs, line breaks, and
-- non-breaking spaces folded to single spaces and trimmed) so a hidden character
-- cannot defeat a keyword match or a trailing space split a later CSV row. The
-- area is the true geodesic ground area (ST_Area_Spheroid on the WGS84 geometry,
-- in square metres), not the service's projection-inflated Shape__Area; it is
-- carried as an exact DECIMAL(18,4) so every downstream SUM is order-independent
-- and the golden output is byte-stable.

CREATE TABLE zoning_tagged AS
WITH norm AS (
  SELECT
    OBJECTID,
    ZONE,
    trim(regexp_replace(replace(coalesce(DESCRIPTION, ''), chr(160), ' '), '\s+', ' ', 'g')) AS description,
    CAST(ST_Area_Spheroid(geom) AS DECIMAL(18,4)) AS area_m2,
    geom
  FROM zoning_raw
),
cls AS (
  SELECT
    OBJECTID,
    ZONE,
    description,
    area_m2,
    geom,
    UPPER(description) AS d
  FROM norm
),
classified AS (
  SELECT
    OBJECTID,
    ZONE,
    description,
    area_m2,
    geom,
    CASE
      WHEN ZONE IS NULL THEN 'Unspecified'
      WHEN (d LIKE '%INDUSTR%' OR d LIKE '%SALVAGE%' OR d LIKE '%MATERIALS%'
            OR d LIKE '%AEROTECH%' OR d LIKE '%AIRPORT%' OR d LIKE '%EMPLOYMENT%'
            OR d LIKE '%BUSINESS PARK%' OR d LIKE '%BUSINESS CAMPUS%' OR d LIKE '%BUSINESS INDUSTRY%')
           AND d NOT LIKE '%FISHING%' AND d NOT LIKE '%TOURIST%' THEN 'Industrial'
      WHEN d LIKE '%RURAL%' OR d LIKE '%RESOURCE%' OR d LIKE '%FISHING%'
            OR d LIKE '%RURAL SETTLEMENT%' OR d LIKE '%EQUINE%' OR d LIKE '%AGRICULT%'
            OR ZONE LIKE 'MR%' OR ZONE = 'RE' THEN 'Rural and Resource'
      WHEN d LIKE '%MIXED USE%' OR d LIKE '%MIXED-USE%' OR d LIKE '%LIVE-WORK%'
            OR d LIKE '%LIVE WORK%' OR d LIKE '%MIXED OPPORTUNITY%'
            OR d LIKE '%CORRIDOR%' OR d LIKE '%DOWNTOWN%'
            OR (d LIKE '%RESIDENTIAL%' AND (d LIKE '%COMMERCIAL%' OR d LIKE '%BUSINESS%'))
            OR ZONE IN ('CEN-1','CEN-2','BW-CEN','US') THEN 'Mixed Use'
      WHEN (d LIKE '%INSTITUTIONAL%' OR d LIKE '%UNIVERSITY%' OR d LIKE '%COLLEGE%'
            OR d LIKE '%HOSPITAL%' OR d LIKE '%DND%' OR d LIKE '%NATIONAL DEFEN%'
            OR d LIKE '%CULTURAL%' OR d LIKE '%COMMUNITY FACILITY%'
            OR d LIKE '%COMMUNITY FACILITIES%' OR d LIKE '%SPECIAL FACILITY%'
            OR d LIKE '%EXHIBITION%' OR d LIKE '%UTILITIES%' OR ZONE IN ('S','SI'))
           AND d NOT LIKE '%PARK%' THEN 'Institutional'
      WHEN (d LIKE '%COMMERCIAL%' OR d LIKE '%BUSINESS%' OR d LIKE '%SHOPPING%'
            OR d LIKE '%RETAIL%' OR d LIKE '%TOURIST%' OR d LIKE '%LARGE SCALE%'
            OR d LIKE '%MAINSTREET%' OR d LIKE '%MAIN STREET%')
           AND d NOT LIKE '%DWELLING%' THEN 'Commercial'
      WHEN d LIKE '%RESIDENTIAL%' OR d LIKE '%DWELLING%' OR d LIKE '%SINGLE FAMILY%'
            OR d LIKE '%SINGLE UNIT%' OR d LIKE '%TWO FAMILY%' OR d LIKE '%TWO UNIT%'
            OR d LIKE '%TOWNHOUSE%' OR d LIKE '%MULTIPLE%' OR d LIKE '%MULTI-UNIT%'
            OR d LIKE '%MULTI UNIT%' OR d LIKE '%APARTMENT%' OR d LIKE '%CLUSTER%'
            OR d LIKE '%MOBILE%' OR d LIKE '%HOUSING%' OR d LIKE '%HOME OCCUPATION%'
            OR d LIKE '%HOME BUSINESS%' THEN 'Residential'
      WHEN d LIKE '%PARK%' OR d LIKE '%OPEN SPACE%'
            OR (d LIKE '%CONSERVATION%' AND d NOT LIKE '%HERITAGE%')
            OR d LIKE '%RECREATION%' OR d LIKE '%FLOODPLAIN%' OR d LIKE '%FLOODWAY%'
            OR d LIKE '%FLOOD PLAIN%' OR d LIKE '%PRESERVATION%' OR d LIKE '%PRESERVE%'
            OR d LIKE '%PROTECTED%' OR d LIKE '%WATER SUPPLY%' OR d LIKE '%WATER ACCESS%'
            OR d LIKE '%ENVIRONMENTAL%' OR d LIKE '%ISLANDS%' OR d LIKE '%HAZARD%'
            OR d LIKE '%COASTAL%' OR d LIKE '%WESTERN COMMON%' THEN 'Park and Open Space'
      ELSE 'Other'
    END AS zone_class
  FROM cls
)
SELECT
  c.OBJECTID,
  c.ZONE,
  c.description,
  c.zone_class,
  c.area_m2,
  COALESCE(g.GSA_NAME, 'Unassigned') AS community,
  c.geom
FROM classified c
LEFT JOIN gsa_raw g
  ON ST_Within(ST_Centroid(c.geom), g.geom)
QUALIFY ROW_NUMBER() OVER (PARTITION BY c.OBJECTID ORDER BY g.GSA_NAME) = 1;

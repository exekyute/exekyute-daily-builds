-- 02_transform.sql
-- Question this step answers: what does one clean, typed device record and one
-- clean segment record look like?
-- Points: the source location text can carry stray line breaks, tabs, trailing
-- spaces, and non-breaking spaces that would otherwise split a CSV row or leave a
-- hidden character on a value (one traffic control location ships with a trailing
-- space, for example). The norm CTE folds every run of whitespace (space, tab, CR,
-- LF, and the non-breaking space chr(160)) down to a single space and trims the
-- location once, so a plain trim of spaces is no longer relied on. install_year is
-- cast to INTEGER (an empty string becomes NULL, kept as NULL because many control
-- locations carry no install year in the source), and latitude and longitude are
-- rounded to six decimals (about 0.1 m), ample for a city map and byte-stable in
-- the CSV. The coded device value is decoded to its published domain label: the
-- signs are all SPDSGN (Speed Display Sign); the control locations map their
-- CONTROL_TYPE integer to the traffic-control label. All 780 point records are
-- kept; no status filter is applied, so the counts stay 73 and 707 as published.
-- Lines: nothing needs cleaning. speed_limit is the posted limit (NULL where the
-- source has none) and len_m is the published segment length in metres.

CREATE TABLE points_clean AS
WITH norm AS (
  SELECT
    source_layer,
    device_code,
    trim(regexp_replace(replace(coalesce(location, ''), chr(160), ' '), '\s+', ' ', 'g')) AS location,
    install_year,
    lat,
    lon
  FROM points_raw
)
SELECT
  source_layer,
  CASE
    WHEN source_layer = 'Speed Display Sign' THEN
      CASE device_code
        WHEN 'BANNER' THEN 'Banner Sign'
        WHEN 'COMMUN' THEN 'Community Sign'
        WHEN 'CULBLD' THEN 'Cultural Sign Blade'
        WHEN 'GATEWA' THEN 'Gateway Sign'
        WHEN 'DIS'    THEN 'Digital Information Sign'
        WHEN 'GDS'    THEN 'Guide Sign'
        WHEN 'WNS'    THEN 'Warning Sign'
        WHEN 'PARK'   THEN 'Park Identification Sign'
        WHEN 'NEIGHB' THEN 'Neighbourhood Identification Sign'
        WHEN 'SPDSGN' THEN 'Speed Display Sign'
        ELSE 'Other (' || device_code || ')'
      END
    ELSE
      CASE device_code
        WHEN '1'  THEN 'Intersection'
        WHEN '6'  THEN 'Signalized Intersection'
        WHEN '7'  THEN 'RA-5 with Flashing Beacon'
        WHEN '8'  THEN 'Overhead Flashing Beacon'
        WHEN '9'  THEN 'RA-5 without Flashing Beacon'
        WHEN '10' THEN 'Rectangular Rapid Flashing Beacon'
        WHEN '11' THEN 'Roundabout'
        WHEN '12' THEN 'Lane Control'
        WHEN '13' THEN 'All Way Stop'
        WHEN '14' THEN 'Pedestrian Half Signals'
        WHEN '15' THEN 'Median Mounted Flashing Beacon'
        ELSE 'Other (' || device_code || ')'
      END
  END AS device_type,
  CAST(NULLIF(install_year, '') AS INTEGER) AS install_year,
  location,
  round(lat, 6) AS lat,
  round(lon, 6) AS lon
FROM norm;

CREATE TABLE lines_clean AS
SELECT
  speed_limit,
  len_m
FROM lines_raw;

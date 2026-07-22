-- 02_transform.sql
-- Question this step answers: what does one clean, typed record look like in
-- each of the three layers?
-- The source free-text fields can carry stray line breaks, tabs, trailing
-- spaces, and non-breaking spaces that would otherwise split a CSV row or leave
-- a hidden character on a value. Each text field is folded: every run of
-- whitespace (space, tab, CR, LF, and the non-breaking space chr(160)) collapses
-- to a single space and the field is trimmed once. The accessibility code is
-- reduced to a 0/1 flag (1 only when the stop is coded 'A', Accessible; the
-- other coded values 'N' Non-Standard and 'I' Inaccessible are not accessible),
-- and every coordinate is rounded to six decimals (about 0.1 m), which is ample
-- for a city map and makes the CSV byte-stable. Stops keep their status code
-- verbatim. Shelters keep only the id, the linked bus-stop id, and the location.

CREATE TABLE stops_clean AS
WITH norm AS (
  SELECT
    trim(regexp_replace(replace(coalesce(busstopid,  ''), chr(160), ' '), '\s+', ' ', 'g')) AS busstopid,
    trim(regexp_replace(replace(coalesce(stopnumber, ''), chr(160), ' '), '\s+', ' ', 'g')) AS stopnumber,
    trim(regexp_replace(replace(coalesce(location,   ''), chr(160), ' '), '\s+', ' ', 'g')) AS location,
    trim(coalesce(accessible, '')) AS accessible,
    trim(coalesce(busstatus,  '')) AS busstatus,
    lat,
    lon
  FROM stops_raw
)
SELECT
  busstopid,
  stopnumber,
  location,
  CASE WHEN accessible = 'A' THEN 1 ELSE 0 END AS accessible,
  busstatus AS status,
  round(lat, 6) AS lat,
  round(lon, 6) AS lon
FROM norm
WHERE busstopid <> '';

CREATE TABLE shelters_clean AS
SELECT
  trim(regexp_replace(replace(coalesce(shelterid, ''), chr(160), ' '), '\s+', ' ', 'g')) AS shelterid,
  trim(regexp_replace(replace(coalesce(busstopid, ''), chr(160), ' '), '\s+', ' ', 'g')) AS busstopid,
  trim(regexp_replace(replace(coalesce(location,  ''), chr(160), ' '), '\s+', ' ', 'g')) AS location
FROM shelters_raw;

CREATE TABLE parkride_clean AS
SELECT
  trim(regexp_replace(replace(coalesce(name,   ''), chr(160), ' '), '\s+', ' ', 'g')) AS name,
  capacity,
  trim(regexp_replace(replace(coalesce(routes, ''), chr(160), ' '), '\s+', ' ', 'g')) AS routes,
  round(lat, 6) AS lat,
  round(lon, 6) AS lon
FROM parkride_raw;

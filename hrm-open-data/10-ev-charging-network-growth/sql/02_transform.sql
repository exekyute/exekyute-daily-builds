-- 02_transform.sql
-- Question this step answers: what does one clean, typed charger record look
-- like?
-- The source free-text fields can carry stray line breaks, tabs, trailing
-- spaces, and non-breaking spaces that would otherwise split a CSV row or leave
-- a hidden character on a value (one location record ships with a trailing
-- space, for example). The norm CTE folds every run of whitespace (space, tab,
-- CR, LF, and the non-breaking space chr(160)) down to a single space and trims
-- each text field once, so a plain trim of spaces is no longer relied on. The
-- final SELECT then casts the install year and quantity to integers, rounds the
-- power rating and the coordinates, and keeps the location text verbatim apart
-- from that whitespace fold. Only installed stations (ASSETSTAT = 'INS') are
-- kept, and rows missing a station id, install year, or charging level are
-- dropped as a guard; the current snapshot loses none.

CREATE TABLE ev_clean AS
WITH norm AS (
  SELECT
    objectid,
    trim(regexp_replace(replace(coalesce(evcsid,     ''), chr(160), ' '), '\s+', ' ', 'g')) AS evcsid,
    trim(regexp_replace(replace(coalesce(owner,      ''), chr(160), ' '), '\s+', ' ', 'g')) AS owner,
    trim(regexp_replace(replace(coalesce(chartype,   ''), chr(160), ' '), '\s+', ' ', 'g')) AS chartype,
    trim(regexp_replace(replace(coalesce(connectype, ''), chr(160), ' '), '\s+', ' ', 'g')) AS connectype,
    trim(regexp_replace(replace(coalesce(location,   ''), chr(160), ' '), '\s+', ' ', 'g')) AS location,
    trim(regexp_replace(replace(coalesce(access,     ''), chr(160), ' '), '\s+', ' ', 'g')) AS access,
    trim(regexp_replace(replace(coalesce(assetstat,  ''), chr(160), ' '), '\s+', ' ', 'g')) AS assetstat,
    trim(regexp_replace(replace(coalesce(instyr,     ''), chr(160), ' '), '\s+', ' ', 'g')) AS instyr,
    trim(regexp_replace(replace(coalesce(quantity,   ''), chr(160), ' '), '\s+', ' ', 'g')) AS quantity,
    power,
    lat,
    lon
  FROM ev_raw
)
SELECT
  objectid,
  evcsid,
  owner,
  chartype,
  connectype,
  round(power, 2) AS power_kw,
  location,
  access,
  CAST(instyr AS INTEGER)   AS install_year,
  CAST(quantity AS INTEGER) AS quantity,
  round(lat, 6) AS lat,
  round(lon, 6) AS lon
FROM norm
WHERE assetstat = 'INS'
  AND evcsid <> ''
  AND instyr <> ''
  AND chartype <> '';

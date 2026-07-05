-- 02_transform.sql
-- Question this step answers: what does one clean, typed row per offence-year
-- look like?
-- Trim the text fields, cast year and convictions to integers, and drop any row
-- missing a key value. Then collapse to exactly one row per offence and year by
-- summing convictions, so a stray duplicate could never double-count or make
-- the later window functions non-deterministic.

CREATE TABLE mva_clean AS
SELECT
  trim(offence_statute)                 AS offence_statute,
  trim(description)                     AS description,
  CAST(trim(year_convicted) AS INTEGER) AS year_convicted,
  CAST(trim(convictions)    AS INTEGER) AS convictions
FROM mva_raw
WHERE offence_statute IS NOT NULL AND trim(offence_statute) <> ''
  AND year_convicted  IS NOT NULL AND trim(year_convicted)  <> ''
  AND convictions     IS NOT NULL AND trim(convictions)     <> '';

CREATE TABLE mva_yearly AS
SELECT
  offence_statute,
  description,
  year_convicted,
  SUM(convictions) AS convictions
FROM mva_clean
GROUP BY offence_statute, description, year_convicted;

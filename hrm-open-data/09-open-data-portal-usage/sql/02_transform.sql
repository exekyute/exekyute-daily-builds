-- 02_transform.sql
-- Question this step answers: what does one clean, typed row per dataset-month
-- look like?
-- Cast month_start to a real DATE and usage to an integer, trim the dataset
-- name, and drop any row missing a key value or carrying a non-positive count.
-- Then collapse to exactly one row per dataset and month by summing usage, so a
-- stray duplicate could never double-count a month or skew a rank. The pull step
-- already rolled the 639,108 live rows to this grain (see SOURCE.md); this guard
-- keeps the pipeline deterministic even if the snapshot were re-cut differently.

CREATE TABLE oda_clean AS
SELECT
  trim(dataset)             AS dataset,
  CAST(month_start AS DATE) AS month_start,
  CAST(usage AS INTEGER)    AS usage
FROM oda_raw
WHERE dataset     IS NOT NULL AND trim(dataset)     <> ''
  AND month_start IS NOT NULL AND trim(month_start) <> ''
  AND usage       IS NOT NULL AND trim(usage)       <> ''
  AND CAST(usage AS INTEGER) > 0;

-- Guard: one row per (dataset, month_start).
CREATE TABLE oda_month AS
SELECT
  dataset,
  month_start,
  SUM(usage) AS usage
FROM oda_clean
GROUP BY dataset, month_start;

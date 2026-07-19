-- 03_analysis.sql
-- The analytical core. Four questions, four tables, then one stacked report.
-- Percent and average columns are formatted to one decimal with printf so the
-- exported text is identical on every run.

-- Question A: how many assets sit in each freshness bucket?
-- The VALUES scaffold pins all five buckets in age order, so a bucket that is
-- empty in this snapshot (No date has no rows here) still appears with a zero
-- count instead of silently vanishing from the report.
CREATE TABLE bucket_summary AS
WITH total AS (
  SELECT count(*) AS n_total FROM asset_audit
),
scaffold (bucket, row_rank) AS (
  VALUES ('Fresh', 1), ('Aging', 2), ('Stale', 3), ('Dormant', 4), ('No date', 5)
),
counts AS (
  SELECT bucket, count(*) AS n_assets, avg(age_months) AS avg_age
  FROM asset_audit
  GROUP BY bucket
)
SELECT
  s.bucket                                              AS item,
  coalesce(c.n_assets, 0)                               AS n_assets,
  printf('%.1f', 100.0 * coalesce(c.n_assets, 0) / t.n_total) AS pct,
  CASE WHEN c.avg_age IS NULL THEN '' ELSE printf('%.1f', c.avg_age) END
                                                        AS age_months,
  s.row_rank                                            AS row_rank
FROM scaffold s
LEFT JOIN counts c ON s.bucket = c.bucket
CROSS JOIN total t;

-- Question B: which categories carry the most stale weight?
-- pct is the share of the category's own assets that are stale or dormant, so
-- a small category of ten abandoned charts ranks above a large healthy one.
-- Ties break by asset count, then name, so the ranking is deterministic.
CREATE TABLE by_category AS
WITH g AS (
  SELECT
    category               AS item,
    count(*)               AS n_assets,
    sum(stale_or_dormant)  AS n_stale_dormant,
    avg(age_months)        AS avg_age
  FROM asset_audit
  GROUP BY category
)
SELECT
  item,
  n_assets,
  n_stale_dormant,
  printf('%.1f', 100.0 * n_stale_dormant / n_assets) AS pct,
  CASE WHEN avg_age IS NULL THEN '' ELSE printf('%.1f', avg_age) END AS age_months,
  ROW_NUMBER() OVER (
    ORDER BY 100.0 * n_stale_dormant / n_assets DESC, n_assets DESC, item
  ) AS row_rank
FROM g;

-- Question C: which owning departments carry the most stale weight?
-- Same shape as Question B, keyed on the owning department instead.
CREATE TABLE by_owner AS
WITH g AS (
  SELECT
    owner                  AS item,
    count(*)               AS n_assets,
    sum(stale_or_dormant)  AS n_stale_dormant,
    avg(age_months)        AS avg_age
  FROM asset_audit
  GROUP BY owner
)
SELECT
  item,
  n_assets,
  n_stale_dormant,
  printf('%.1f', 100.0 * n_stale_dormant / n_assets) AS pct,
  CASE WHEN avg_age IS NULL THEN '' ELSE printf('%.1f', avg_age) END AS age_months,
  ROW_NUMBER() OVER (
    ORDER BY 100.0 * n_stale_dormant / n_assets DESC, n_assets DESC, item
  ) AS row_rank
FROM g;

-- Question D: which individual assets have gone longest without an update?
-- Restricted to type = dataset with a usable date: datasets are the assets a
-- publisher is expected to maintain, where charts, filters, and stories are
-- derived views. Oldest first; ties break by exact date, then name.
CREATE TABLE worst_offenders AS
WITH ranked AS (
  SELECT
    name         AS item,
    owner        AS detail,
    age_months,
    last_updated,
    ROW_NUMBER() OVER (
      ORDER BY age_months DESC, last_updated, name
    ) AS row_rank
  FROM asset_audit
  WHERE type = 'dataset' AND last_updated IS NOT NULL
)
SELECT item, detail, age_months, last_updated, row_rank
FROM ranked
WHERE row_rank <= 15;

-- The stacked report: every section in one table with one shared column set,
-- everything cast to VARCHAR so empty cells export as truly empty fields.
-- This is the table 99_export writes and the golden diff checks.
CREATE TABLE freshness_audit AS
SELECT
  'overall'                                     AS section,
  'all assets'                                  AS item,
  ''                                            AS detail,
  CAST(count(*) AS VARCHAR)                     AS n_assets,
  CAST(sum(stale_or_dormant) AS VARCHAR)        AS n_stale_dormant,
  printf('%.1f', 100.0 * sum(stale_or_dormant) / count(*)) AS pct,
  printf('%.1f', avg(age_months))               AS age_months,
  ''                                            AS last_updated,
  1                                             AS row_rank
FROM asset_audit
UNION ALL
SELECT
  'bucket_summary', item, '', CAST(n_assets AS VARCHAR), '',
  pct, age_months, '', row_rank
FROM bucket_summary
UNION ALL
SELECT
  'by_category', item, '', CAST(n_assets AS VARCHAR),
  CAST(n_stale_dormant AS VARCHAR), pct, age_months, '', row_rank
FROM by_category
UNION ALL
SELECT
  'by_owner', item, '', CAST(n_assets AS VARCHAR),
  CAST(n_stale_dormant AS VARCHAR), pct, age_months, '', row_rank
FROM by_owner
UNION ALL
SELECT
  'worst_offenders', item, detail, '', '',
  '', CAST(age_months AS VARCHAR), CAST(last_updated AS VARCHAR), row_rank
FROM worst_offenders;

-- The headline: two ready-to-read lines for the console. run.py prints these;
-- it does not compute them.
CREATE TABLE headline AS
SELECT
  1 AS ord,
  CAST(sum(stale_or_dormant) AS VARCHAR) || ' of ' || CAST(count(*) AS VARCHAR)
    || ' catalogued assets ('
    || printf('%.1f', 100.0 * sum(stale_or_dormant) / count(*))
    || '%) are stale or dormant: no data update in the 12 months before the pull date 2026-07-06.'
    AS line
FROM asset_audit
UNION ALL
SELECT
  2 AS ord,
  'Oldest maintained dataset: ' || item || ' (' || detail || '), last updated '
    || CAST(last_updated AS VARCHAR) || ', ' || CAST(age_months AS VARCHAR)
    || ' months before the pull date.'
    AS line
FROM worst_offenders
WHERE row_rank = 1
ORDER BY ord;

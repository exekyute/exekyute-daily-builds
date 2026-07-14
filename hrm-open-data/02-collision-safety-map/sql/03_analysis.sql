-- 03_analysis.sql
-- The analytical core. Two result tables plus a headline table.
--
-- Determinism note: the "latest full year" is derived from a literal pull-date
-- constant, DATE '2026-07-09', never CURRENT_DATE. The pull year (2026) is only
-- partway through on the pull date, so the latest full year is the year before
-- it, 2025. Fixing the constant keeps the headline reproducible on any future
-- run of the same snapshot.

-- Question A: for each year, how many collisions were there, and what share
-- involved each contributing factor?
-- The factor columns are already 0/1 integers, so a SUM is a count and a mean
-- times 100 is a percent. Percents are rounded to one decimal so the file is
-- byte-for-byte stable. Both the raw counts and the shares are kept: the counts
-- are the ground truth the dashboard re-derives its headline from, the shares
-- are what the Power BI cards and the trend read.
CREATE TABLE collisions_by_year AS
SELECT
  year,
  count(*)                                             AS collisions,
  SUM(PEDESTRIAN_COLLISIONS)                           AS pedestrian,
  SUM(BICYCLE_COLLISIONS)                              AS bicycle,
  SUM(IMPAIRED_DRIVING)                                AS impaired,
  SUM(DISTRACTED_DRIVING)                              AS distracted,
  SUM(INTERSECTION_RELATED)                            AS intersection,
  SUM(FATAL_INJURY)                                    AS fatal,
  round(100.0 * SUM(PEDESTRIAN_COLLISIONS) / count(*), 1) AS pct_pedestrian,
  round(100.0 * SUM(BICYCLE_COLLISIONS)    / count(*), 1) AS pct_bicycle,
  round(100.0 * SUM(IMPAIRED_DRIVING)      / count(*), 1) AS pct_impaired,
  round(100.0 * SUM(DISTRACTED_DRIVING)    / count(*), 1) AS pct_distracted,
  round(100.0 * SUM(INTERSECTION_RELATED)  / count(*), 1) AS pct_intersection,
  round(100.0 * SUM(FATAL_INJURY)          / count(*), 1) AS pct_fatal
FROM collisions_clean
GROUP BY year;

-- Question B: when in the day and the year do collisions land?
-- One row per hour of day (0 to 23), one column per calendar month, each cell a
-- collision count. This is the month-by-hour matrix the Tableau calendar
-- heatmap and the browser heatmap both draw, frozen here so the figures are
-- fixed. Conditional sums pivot month into the twelve columns.
CREATE TABLE collisions_month_hour AS
SELECT
  hour,
  SUM(CASE WHEN month =  1 THEN 1 ELSE 0 END) AS m01,
  SUM(CASE WHEN month =  2 THEN 1 ELSE 0 END) AS m02,
  SUM(CASE WHEN month =  3 THEN 1 ELSE 0 END) AS m03,
  SUM(CASE WHEN month =  4 THEN 1 ELSE 0 END) AS m04,
  SUM(CASE WHEN month =  5 THEN 1 ELSE 0 END) AS m05,
  SUM(CASE WHEN month =  6 THEN 1 ELSE 0 END) AS m06,
  SUM(CASE WHEN month =  7 THEN 1 ELSE 0 END) AS m07,
  SUM(CASE WHEN month =  8 THEN 1 ELSE 0 END) AS m08,
  SUM(CASE WHEN month =  9 THEN 1 ELSE 0 END) AS m09,
  SUM(CASE WHEN month = 10 THEN 1 ELSE 0 END) AS m10,
  SUM(CASE WHEN month = 11 THEN 1 ELSE 0 END) AS m11,
  SUM(CASE WHEN month = 12 THEN 1 ELSE 0 END) AS m12
FROM collisions_clean
GROUP BY hour;

-- Question C (headline): in the latest full year, how many collisions were
-- there, and how many involved a pedestrian?
-- Two ready-to-read lines for the console. year(DATE '2026-07-09') - 1 = 2025 is
-- the latest full year on the pull date.
CREATE TABLE headline AS
WITH y AS (
  SELECT year(DATE '2026-07-09') - 1 AS latest_full_year
),
agg AS (
  SELECT
    y.latest_full_year,
    count(*)                   AS collisions,
    SUM(PEDESTRIAN_COLLISIONS) AS pedestrian
  FROM collisions_clean c
  CROSS JOIN y
  WHERE c.year = y.latest_full_year
  GROUP BY y.latest_full_year
)
SELECT 1 AS ord,
  'Latest full year ' || latest_full_year || ': '
    || format('{:,}', collisions) || ' collisions.' AS line
FROM agg
UNION ALL
SELECT 2 AS ord,
  'Pedestrian-involved in ' || latest_full_year || ': '
    || format('{:,}', pedestrian) || ' ('
    || round(100.0 * pedestrian / collisions, 1) || ' percent of the year).' AS line
FROM agg
ORDER BY ord;

-- 03_analysis.sql
-- The analytical core. Two marts plus a headline.

-- Mart A: mart_usage_monthly (one row per month).
-- Question: how much usage did the Hub draw each month, and across how many
-- distinct datasets?
-- total_usage sums every dataset's hits in the month. distinct_datasets counts
-- how many datasets drew at least one hit that month (the usage > 0 filter in
-- 02_transform means a dataset only counts in months it actually saw traffic).
CREATE TABLE mart_usage_monthly AS
SELECT
  month_start,
  CAST(year(month_start) AS INTEGER) AS year,
  SUM(usage)              AS total_usage,
  COUNT(DISTINCT dataset) AS distinct_datasets
FROM oda_month
GROUP BY month_start;

-- Mart B: mart_usage_by_dataset (one row per dataset).
-- Question: which datasets draw the most usage over the whole window, and when
-- did each first and last draw traffic?
-- usage_rank ranks datasets by total_usage, highest first. RANK gives tied
-- totals the same rank and then skips, which mirrors the Power BI
-- RANKX(..., DESC, Skip) measure so the two agree row for row.
CREATE TABLE mart_usage_by_dataset AS
SELECT
  dataset,
  SUM(usage)       AS total_usage,
  MIN(month_start) AS first_month,
  MAX(month_start) AS last_month,
  RANK() OVER (ORDER BY SUM(usage) DESC) AS usage_rank
FROM oda_month
GROUP BY dataset;

-- Headline (two rows): the total recorded usage across the window and the single
-- most-used dataset, as ready-to-read lines for the console. run.py prints
-- these; it does not compute them.
CREATE TABLE headline AS
WITH totals AS (
  SELECT
    SUM(total_usage)      AS total_usage,
    MIN(month_start)      AS first_month,
    MAX(month_start)      AS last_month,
    COUNT(*)              AS n_months
  FROM mart_usage_monthly
),
top AS (
  SELECT dataset, total_usage
  FROM mart_usage_by_dataset
  WHERE usage_rank = 1
)
SELECT
  1 AS ord,
  'Total recorded open-data usage across the window: ' || totals.total_usage
    || ' hits over ' || totals.n_months || ' months, '
    || strftime(totals.first_month, '%Y-%m') || ' to '
    || strftime(totals.last_month, '%Y-%m') || '.' AS line
FROM totals
UNION ALL
SELECT
  2 AS ord,
  'Most-used dataset: ' || top.dataset || ' (' || top.total_usage
    || ' hits, rank 1 of ' || (SELECT COUNT(*) FROM mart_usage_by_dataset) || ').' AS line
FROM top
ORDER BY ord;

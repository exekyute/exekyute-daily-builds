-- 03_analysis.sql
-- The analytical core. Roll the half-hour intervals up to months, roll the
-- months up to years, attach each month to its year, and name the latest full
-- year as a ready-to-read headline. Every rate is stored as a fraction in [0, 1]
-- rounded to four decimals; a fraction of 0.0275 is 2.75 percent. Talk time is in
-- seconds. Every ratio guards its denominator so a zero-offered month can never
-- divide by zero (the current snapshot has none, so the guard never fires).

-- Question A: for each calendar month, how many calls were offered, handled, and
-- abandoned, how long was the talk time, and what were the derived service rates?
CREATE TABLE calls_monthly AS
SELECT
  CAST(date_trunc('month', call_date) AS DATE) AS month_start,
  year(call_date)                              AS year,
  month(call_date)                             AS month,
  SUM(offered)                                 AS offered,
  SUM(handled)                                 AS handled,
  SUM(abandoned)                               AS abandoned,
  SUM(processed_in_ivr)                        AS processed_in_ivr,
  SUM(total_talk_time)                         AS total_talk_time,
  CASE WHEN SUM(offered) = 0 THEN NULL
       ELSE round(SUM(abandoned)::DOUBLE / SUM(offered), 4) END AS abandonment_rate,
  CASE WHEN SUM(offered) = 0 THEN NULL
       ELSE round(SUM(handled)::DOUBLE / SUM(offered), 4) END   AS answer_rate,
  CASE WHEN SUM(handled) = 0 THEN NULL
       ELSE round(SUM(total_talk_time)::DOUBLE / SUM(handled), 1) END AS avg_talk_time
FROM calls_clean
GROUP BY 1, 2, 3;

-- Question B: rolled up to the whole year, what were the totals and the year-level
-- service rates? The year abandonment rate is the ratio of summed counts, not the
-- average of the monthly rates, so it weights by call volume.
CREATE TABLE calls_yearly AS
SELECT
  year,
  SUM(offered)          AS year_offered,
  SUM(handled)          AS year_handled,
  SUM(abandoned)        AS year_abandoned,
  SUM(processed_in_ivr) AS year_processed_in_ivr,
  SUM(total_talk_time)  AS year_total_talk_time,
  CASE WHEN SUM(offered) = 0 THEN NULL
       ELSE round(SUM(abandoned)::DOUBLE / SUM(offered), 4) END AS year_abandonment_rate,
  CASE WHEN SUM(offered) = 0 THEN NULL
       ELSE round(SUM(handled)::DOUBLE / SUM(offered), 4) END   AS year_answer_rate
FROM calls_monthly
GROUP BY year;

-- Question C: the exported table. One row per month, carrying that month's figures
-- and the totals and rates for the year it belongs to. The year columns repeat on
-- every month of a given year, which lets a reader see a month against its year
-- without a second lookup.
CREATE TABLE monthly_service_levels AS
SELECT
  m.month_start,
  m.year,
  m.month,
  m.offered,
  m.handled,
  m.abandoned,
  m.processed_in_ivr,
  m.total_talk_time,
  m.abandonment_rate,
  m.answer_rate,
  m.avg_talk_time,
  y.year_offered,
  y.year_handled,
  y.year_abandoned,
  y.year_processed_in_ivr,
  y.year_total_talk_time,
  y.year_abandonment_rate,
  y.year_answer_rate
FROM calls_monthly m
JOIN calls_yearly y USING (year);

-- Question D (headline): name the latest full year (the most recent year with all
-- twelve months present) and read its offered, handled, abandoned totals and the
-- abandonment rate as two ready-to-print lines. run.py prints these; it does not
-- compute them.
CREATE TABLE headline AS
WITH latest_full_year AS (
  SELECT MAX(year) AS y
  FROM (SELECT year FROM calls_monthly GROUP BY year HAVING COUNT(*) = 12)
),
yr AS (
  SELECT * FROM calls_yearly WHERE year = (SELECT y FROM latest_full_year)
)
SELECT
  1 AS ord,
  'Latest full year ' || year || ': ' || year_offered || ' calls offered, '
    || year_handled || ' handled, ' || year_abandoned || ' abandoned.' AS line
FROM yr
UNION ALL
SELECT
  2 AS ord,
  year || ' abandonment rate ' || round(100.0 * year_abandoned / year_offered, 2)
    || ' percent (' || year_abandonment_rate || ' of offered), answer rate '
    || round(100.0 * year_handled / year_offered, 2) || ' percent.' AS line
FROM yr
ORDER BY ord;

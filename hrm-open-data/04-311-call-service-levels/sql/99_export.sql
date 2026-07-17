-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files?
-- Two writes, both ordered by month_start so the row order is byte-stable:
--   1. out/monthly_service_levels.csv is the analytical golden that run.py diffs
--      against expected/. It carries each month plus the totals and rates for the
--      year that month sits in.
--   2. bi/exports/mart_311_monthly.csv is the frozen mart that Tableau and Power
--      BI both read. It is the clean per-month subset: date parts, the five
--      counts, and the three derived per-month figures, and nothing per-year, so
--      each tool aggregates the year itself and both land on the same number.

COPY (
  SELECT *
  FROM monthly_service_levels
  ORDER BY month_start
) TO 'out/monthly_service_levels.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT
    month_start,
    year,
    month,
    offered,
    handled,
    abandoned,
    processed_in_ivr,
    total_talk_time,
    abandonment_rate,
    answer_rate,
    avg_talk_time
  FROM monthly_service_levels
  ORDER BY month_start
) TO 'bi/exports/mart_311_monthly.csv' (HEADER, DELIMITER ',');

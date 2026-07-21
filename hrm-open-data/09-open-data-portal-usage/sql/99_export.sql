-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files?
-- Write both marts twice: once to out/ (diffed against the golden in expected/)
-- and once to bi/exports/ (the frozen copy Power BI imports). The two writes come
-- from the same tables with the same ORDER BY, so the golden and the BI mart are
-- byte-for-byte identical and Power BI binds to the exact figures the SQL
-- verified. The ORDER BY on each query fixes row order so the output is
-- reproducible against expected/.

-- Mart A: the monthly usage series, oldest month first.
COPY (
  SELECT month_start, year, total_usage, distinct_datasets
  FROM mart_usage_monthly
  ORDER BY month_start
) TO 'out/mart_usage_monthly.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT month_start, year, total_usage, distinct_datasets
  FROM mart_usage_monthly
  ORDER BY month_start
) TO 'bi/exports/mart_usage_monthly.csv' (HEADER, DELIMITER ',');

-- Mart B: datasets ranked by total usage, most-used first, ties broken by name.
COPY (
  SELECT dataset, total_usage, first_month, last_month, usage_rank
  FROM mart_usage_by_dataset
  ORDER BY total_usage DESC, dataset
) TO 'out/mart_usage_by_dataset.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT dataset, total_usage, first_month, last_month, usage_rank
  FROM mart_usage_by_dataset
  ORDER BY total_usage DESC, dataset
) TO 'bi/exports/mart_usage_by_dataset.csv' (HEADER, DELIMITER ',');

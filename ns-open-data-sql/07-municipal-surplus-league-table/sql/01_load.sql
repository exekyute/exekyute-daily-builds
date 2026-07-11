-- 01_load.sql
-- Question: what raw rows are we working from?
-- Loads the pinned, date-stamped snapshot of the Municipal Fiscal Statistics
-- Operating Fund dataset (Socrata 4x4 sbzw-ajrm). Every column is read as text so
-- that numeric casting is explicit and controlled in 02_transform.sql, and so a
-- blank money field arrives as NULL rather than a silent zero.

CREATE TABLE raw_operating_fund AS
SELECT *
FROM read_csv_auto(
  'data/raw/ns_municipal-operating-fund_2026-07-05.csv',
  header = true,
  all_varchar = true
);

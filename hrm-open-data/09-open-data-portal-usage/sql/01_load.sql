-- 01_load.sql
-- Question this step answers: what rows are in the pinned snapshot?
-- Read the committed snapshot straight into the raw table. Columns are pinned
-- to VARCHAR so the load never depends on type auto-detection. The path is
-- relative to the project folder, so run.py must be launched from here.

INSERT INTO oda_raw
SELECT dataset, month_start, usage
FROM read_csv(
  'data/raw/hrm_open-data-analytics_2026-07-13.csv',
  header  = true,
  columns = {
    'dataset':     'VARCHAR',
    'month_start': 'VARCHAR',
    'usage':       'VARCHAR'
  }
);

-- 01_load.sql
-- Question this step answers: what rows are in the pinned snapshot?
-- Read the committed snapshot straight into the raw table. Columns are pinned
-- to VARCHAR so the load never depends on type auto-detection. The path is
-- relative to the project folder, so run.py must be launched from here.

INSERT INTO mva_raw
SELECT offence_statute, description, year_convicted, convictions
FROM read_csv(
  'data/raw/ns_mva-conviction-trend_2026-07-05.csv',
  header  = true,
  columns = {
    'offence_statute': 'VARCHAR',
    'description':     'VARCHAR',
    'year_convicted':  'VARCHAR',
    'convictions':     'VARCHAR'
  }
);

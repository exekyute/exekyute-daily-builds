-- 01_load.sql
-- Question this step answers: what rows are in the pinned snapshot?
-- Read the committed snapshot straight into the raw table. Columns are pinned to
-- VARCHAR so the load never depends on type auto-detection, and DuckDB maps them
-- by header name (it strips the leading byte-order mark the Hub export adds). The
-- path is relative to the project folder, so run.py must be launched from here.

INSERT INTO calls_raw
SELECT CALL_DATE, MILITARY_HOUR, INTERVAL, OFFERED, HANDLED, ABANDONED,
       PROCESSED_IN_IVR, TOTAL_TALK_TIME, AVERAGE_TALK_TIME, ObjectId
FROM read_csv(
  'data/raw/hrm_311-call-volumes_2026-07-09.csv',
  header  = true,
  columns = {
    'CALL_DATE':         'VARCHAR',
    'MILITARY_HOUR':     'VARCHAR',
    'INTERVAL':          'VARCHAR',
    'OFFERED':           'VARCHAR',
    'HANDLED':           'VARCHAR',
    'ABANDONED':         'VARCHAR',
    'PROCESSED_IN_IVR':  'VARCHAR',
    'TOTAL_TALK_TIME':   'VARCHAR',
    'AVERAGE_TALK_TIME': 'VARCHAR',
    'ObjectId':          'VARCHAR'
  }
);

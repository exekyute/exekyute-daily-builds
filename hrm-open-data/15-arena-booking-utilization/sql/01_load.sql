-- 01_load.sql
-- Question this step answers: what rows are in the pinned snapshot?
-- Read the committed snapshot into the raw table. The Hub CSV headers are the field
-- aliases (Arena Pad Name, Booking Date, Booking Start, Booking End, Event Type,
-- Service), so all_varchar reads every column as text and the SELECT keeps the six
-- fields this build needs by their aliased names. The path is relative to the project
-- folder, so run.py must be launched from here.

INSERT INTO ab_raw
SELECT
  "Arena Pad Name",
  "Booking Date",
  "Booking Start",
  "Booking End",
  "Event Type",
  "Service"
FROM read_csv(
  'data/raw/hrm_arena-bookings_2026-07-13.csv',
  header      = true,
  all_varchar = true
);

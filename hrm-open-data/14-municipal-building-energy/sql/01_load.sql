-- 01_load.sql
-- Question this step answers: what rows are in the pinned snapshot?
-- Read the committed CSV straight into the raw table, projecting only the six
-- columns the build uses out of the twelve the download carries. The source
-- header names carry spaces and the file starts with a byte-order mark, so the
-- columns are selected by their exact quoted header names. Everything lands as
-- VARCHAR so the load never depends on type auto-detection. The path is relative
-- to the project folder, so run.py must be launched from here.

INSERT INTO energy_raw
SELECT
  "Energy Type"                     AS energy_type,
  "Portfolio Manager Property Name" AS building_name,
  "HRM Building ID"                 AS hrm_building_id,
  "Unit of Measure"                 AS unit_of_measure,
  "Consumption"                     AS consumption,
  "Cost"                            AS cost
FROM read_csv(
  'data/raw/hrm_building-energy-usage_2026-07-13.csv',
  header      = true,
  all_varchar = true
);

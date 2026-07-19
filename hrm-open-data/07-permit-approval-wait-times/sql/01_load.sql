-- 01_load.sql
-- Question this step answers: what rows are in the pinned snapshot?
-- Read the committed snapshot into the raw table. The file carries a leading
-- OBJECTID column that this build does not use, so all_varchar reads every
-- column as text and the SELECT keeps only the five fields the mart needs. The
-- path is relative to the project folder, so run.py must be launched from here.

INSERT INTO pt_raw
SELECT
  Permit_Number,
  Issuance_Stage,
  Jurisdictional_Breakdown,
  Total_Occurrence,
  Total_Duration
FROM read_csv(
  'data/raw/hrm_permit-processing-times_2026-07-09.csv',
  header      = true,
  all_varchar = true
);

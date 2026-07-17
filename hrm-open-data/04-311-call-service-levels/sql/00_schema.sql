-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is
-- the raw shape of the source file?
-- Reset every table so a re-run starts from a clean, repeatable state, then
-- declare the raw landing table. Every raw column is VARCHAR because the Hub CSV
-- export delivers every field as text (CALL_DATE arrives as a formatted date
-- string, not epoch ms); typing and date parsing happen in 02_transform.

DROP TABLE IF EXISTS calls_raw;
DROP TABLE IF EXISTS calls_clean;
DROP TABLE IF EXISTS calls_monthly;
DROP TABLE IF EXISTS calls_yearly;
DROP TABLE IF EXISTS monthly_service_levels;
DROP TABLE IF EXISTS headline;

CREATE TABLE calls_raw (
  CALL_DATE         VARCHAR,
  MILITARY_HOUR     VARCHAR,
  INTERVAL          VARCHAR,
  OFFERED           VARCHAR,
  HANDLED           VARCHAR,
  ABANDONED         VARCHAR,
  PROCESSED_IN_IVR  VARCHAR,
  TOTAL_TALK_TIME   VARCHAR,
  AVERAGE_TALK_TIME VARCHAR,
  ObjectId          VARCHAR
);

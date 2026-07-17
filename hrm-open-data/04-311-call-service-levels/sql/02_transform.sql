-- 02_transform.sql
-- Question this step answers: what does one clean, typed half-hour interval row
-- look like, with a real calendar date?
-- The Hub export renders CALL_DATE as a formatted local datetime string such as
-- "1/3/2017 8:00:00 AM". The time portion is a constant display artifact (only
-- 07:00 or 08:00, a daylight-saving offset), well clear of midnight, so the
-- month/day/year is the true call date. Parse it to a DATE, cast the counts, and
-- drop any row whose date fails to parse or whose OFFERED value is missing.

CREATE TABLE calls_clean AS
SELECT
  CAST(try_strptime(CALL_DATE, '%-m/%-d/%Y %-I:%M:%S %p') AS DATE) AS call_date,
  CAST(trim(OFFERED)          AS INTEGER) AS offered,
  CAST(trim(HANDLED)          AS INTEGER) AS handled,
  CAST(trim(ABANDONED)        AS INTEGER) AS abandoned,
  CAST(trim(PROCESSED_IN_IVR) AS INTEGER) AS processed_in_ivr,
  CAST(trim(TOTAL_TALK_TIME)  AS BIGINT)  AS total_talk_time
FROM calls_raw
WHERE try_strptime(CALL_DATE, '%-m/%-d/%Y %-I:%M:%S %p') IS NOT NULL
  AND OFFERED IS NOT NULL AND trim(OFFERED) <> '';

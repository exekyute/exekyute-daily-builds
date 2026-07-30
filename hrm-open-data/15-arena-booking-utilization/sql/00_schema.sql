-- 00_schema.sql
-- Question this step answers: what tables does the pipeline use, and what is the
-- raw shape of the source file?
-- Reset every table so a re-run starts from a clean, repeatable state, then declare
-- the raw landing table. The Hub CSV delivers every field as text, so every raw
-- column is VARCHAR; typing and casting happen in 02_transform. A one-row params
-- table holds the single documented capacity assumption so the constant lives in the
-- SQL as one named value rather than a literal scattered through the analysis.

DROP TABLE IF EXISTS ab_raw;
DROP TABLE IF EXISTS ab_clean;
DROP TABLE IF EXISTS mart_use;
DROP TABLE IF EXISTS facility_month;
DROP TABLE IF EXISTS headline;
DROP TABLE IF EXISTS params;

-- The capacity assumption, held as one named value. OPEN_HOURS_PER_DAY is the
-- nominal number of bookable hours in an arena day. It is a documented constant, not
-- a figure derived from the data, so the utilization proxy is deterministic. See
-- spec.md and data_dictionary.md for what the proxy does and does not mean.
CREATE TABLE params AS SELECT 18::INTEGER AS open_hours_per_day;

-- Raw landing table. Column names are the clean fields this build uses; the CSV
-- carries the source aliases (Arena Pad Name, Booking Date, and so on), which
-- 01_load maps in by name.
CREATE TABLE ab_raw (
  facility      VARCHAR,  -- source "Arena Pad Name": the ice pad, e.g. Scotia One Arena
  booking_date  VARCHAR,  -- source "Booking Date": YYYY-MM-DD
  booking_start VARCHAR,  -- source "Booking Start": local datetime string, e.g. 4/1/2025 10:30:00 AM
  booking_end   VARCHAR,  -- source "Booking End":   local datetime string
  event_type    VARCHAR,  -- source "Event Type": the activity, e.g. Hockey, Figure Skating
  service       VARCHAR   -- source "Service": drives the ice vs dry-floor use type
);

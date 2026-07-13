-- 00_schema.sql
-- Question this step answers: what shape does the raw snapshot have, and where
-- will the cleaned and analytical tables live?
--
-- The source file is a single "long" table that stacks three separate cross-tabs
-- (one broken out by year, one by month, one by sex). Every column arrives as
-- text so nothing is coerced or dropped on load. Cleaning happens in 02_transform.

DROP TABLE IF EXISTS driver_deaths_raw;

CREATE TABLE driver_deaths_raw (
    year                       VARCHAR,  -- calendar year, populated only on the by-year rows
    driver_toxicology_results  VARCHAR,  -- toxicology category label
    frequency                  VARCHAR,  -- count of driver deaths for the row
    percent_annual             VARCHAR,  -- category share within the year (by-year rows)
    percent_total_all_years    VARCHAR,  -- category share across all years (by-month rows)
    month                      VARCHAR,  -- three-letter month, populated only on the by-month rows
    sex                        VARCHAR   -- Male/Female, populated only on the by-sex rows
);

-- Cleaned base table (typed) and the single analytical output table are (re)built
-- by later steps. Drop them here so a re-run starts from a known empty state.
DROP TABLE IF EXISTS driver_deaths;
DROP TABLE IF EXISTS toxicology_trend;

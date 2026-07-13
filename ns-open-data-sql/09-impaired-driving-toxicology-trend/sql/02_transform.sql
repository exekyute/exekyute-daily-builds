-- 02_transform.sql
-- Question this step answers: what is a clean, typed row, and which rows count?
--
-- Cast the two numeric fields, trim the category label, and keep only rows that
-- carry a usable count. Rows without a frequency are dropped here so downstream
-- aggregation never sees a null count. The by-sex slice of the source is not used
-- by this project, so it is filtered out: we keep only the by-year rows
-- (year set, month null) and the by-month rows (month set, year null).

CREATE TABLE driver_deaths AS
SELECT
    TRY_CAST(year AS INTEGER)          AS year,
    TRIM(driver_toxicology_results)    AS category,
    CAST(frequency AS INTEGER)         AS deaths,
    month
FROM driver_deaths_raw
WHERE frequency IS NOT NULL
  AND TRIM(frequency) <> ''
  AND sex IS NULL                       -- exclude the by-sex cross-tab
  AND (
        (year IS NOT NULL AND month IS NULL)   -- by-year rows
     OR (month IS NOT NULL AND year IS NULL)    -- by-month rows
      );

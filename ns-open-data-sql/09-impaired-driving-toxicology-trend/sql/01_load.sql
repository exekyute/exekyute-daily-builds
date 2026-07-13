-- 01_load.sql
-- Question this step answers: how do the pinned snapshot rows get into the database?
--
-- Read the committed, dated snapshot as all-text (all_varchar) so values load
-- exactly as published. The path is relative to the project folder; run.py sets
-- the working directory to that folder before executing this file.

INSERT INTO driver_deaths_raw
SELECT year,
       driver_toxicology_results,
       frequency,
       percent_annual,
       percent_total_all_years,
       month,
       sex
FROM read_csv('data/raw/ns_driver-deaths_2026-07-05.csv',
              header = true,
              all_varchar = true);

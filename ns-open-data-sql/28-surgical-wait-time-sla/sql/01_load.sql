-- 01_load.sql
-- Load the pinned snapshot. The filename carries the pull date; replacing the
-- snapshot means re-baselining expected/wait_time_sla.csv on purpose.

INSERT INTO raw_wait_times
SELECT period, specialty, procedure, provider, zone, facility, year, quarter,
       consult_median, consult_90th, surgery_median, surgery_90th
FROM read_csv(
    'data/raw/ns_surgical-wait-times_2026-07-25.csv',
    header = true,
    all_varchar = true
);

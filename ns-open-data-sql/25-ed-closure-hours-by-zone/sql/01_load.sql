-- 01_load.sql
-- Load the pinned snapshot. The filename carries the pull date; replacing the
-- snapshot means re-baselining expected/ed_closures.csv on purpose.

INSERT INTO raw_closures
SELECT year, zone, type, site, temporary, scheduled, total
FROM read_csv(
    'data/raw/ns_ed-closure-hours_2026-07-25.csv',
    header = true,
    all_varchar = true
);

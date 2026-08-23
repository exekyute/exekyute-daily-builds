-- 01_load.sql
-- Load the pinned snapshot. The filename carries the pull date; replacing the
-- snapshot means re-baselining expected/fish_landings.csv on purpose.

INSERT INTO raw_landings
SELECT year, port, county, kgs, purchase_total
FROM read_csv(
    'data/raw/ns_fish-landings_2026-07-25.csv',
    header = true,
    all_varchar = true
);

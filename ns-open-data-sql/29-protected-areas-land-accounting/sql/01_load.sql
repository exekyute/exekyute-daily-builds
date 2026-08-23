-- 01_load.sql
-- Load the pinned snapshot. The filename carries the pull date; replacing the
-- snapshot means re-baselining expected/protected_areas.csv on purpose.

INSERT INTO raw_protected
SELECT objectid, pro_name, protect1, protect2, owner, authority, status,
       stat_date, lgl_effect, ha_gis, shape_leng, shape_area
FROM read_csv(
    'data/raw/ns_protected-areas_2026-07-25.csv',
    header = true,
    all_varchar = true
);

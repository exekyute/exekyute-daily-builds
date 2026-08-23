-- 00_schema.sql
-- Raw landing table for the committed snapshot. Every column lands as text so
-- that typing happens once, in 02_transform.sql, where a bad value fails the
-- run loudly instead of turning into a silent NULL here.
--
-- The source layer also carries a the_geom MULTIPOLYGON column holding
-- thousands of coordinates per row. It is excluded at the pull (see SOURCE.md)
-- and has no landing column here: this build reads the layer tabularly.

CREATE OR REPLACE TABLE raw_protected (
    objectid   VARCHAR,
    pro_name   VARCHAR,
    protect1   VARCHAR,
    protect2   VARCHAR,
    owner      VARCHAR,
    authority  VARCHAR,
    status     VARCHAR,
    stat_date  VARCHAR,
    lgl_effect VARCHAR,
    ha_gis     VARCHAR,
    shape_leng VARCHAR,
    shape_area VARCHAR
);

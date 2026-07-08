-- Schema for the hatchery stocking summary.
-- Two tables are defined here: a raw staging table that mirrors the CSV column
-- for column as text, and a typed fact table the analysis reads from. Keeping
-- the raw load untyped means every parsing and cleaning decision is visible in
-- 02_transform.sql rather than hidden in a reader's guesswork.

DROP TABLE IF EXISTS stocking_raw;
CREATE TABLE stocking_raw (
    county                       VARCHAR,
    name                         VARCHAR,
    type                         VARCHAR,
    easting                      VARCHAR,
    northing                     VARCHAR,
    primary_stocking_objective   VARCHAR,
    secondary_stocking_objective VARCHAR,
    number_released              VARCHAR,
    stocking_date                VARCHAR,
    growth_stage                 VARCHAR,
    mark                         VARCHAR,
    hatchery                     VARCHAR,
    fish_length_cm               VARCHAR,
    fish_weight_g                VARCHAR,
    stock                        VARCHAR,
    stock_strain                 VARCHAR
);

DROP TABLE IF EXISTS stocking_fact;
CREATE TABLE stocking_fact (
    county          VARCHAR,
    waterbody       VARCHAR,
    waterbody_type  VARCHAR,
    species         VARCHAR,
    stocking_year   INTEGER,
    number_released BIGINT,
    fish_length_cm  DOUBLE,
    fish_weight_g   DOUBLE
);

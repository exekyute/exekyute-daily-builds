-- 00_schema: the raw landing table plus every named constant this build runs on.
--
-- Raw columns land as text so a malformed cell cannot fail the load. Typing and
-- the exclusion accounting happen in 02_transform, where each rejected row is
-- counted rather than dropped in silence.

CREATE OR REPLACE TABLE ltc_raw (
    facility_name                              VARCHAR,
    address                                    VARCHAR,
    town                                       VARCHAR,
    postal_code                                VARCHAR,
    facility_type                              VARCHAR,
    nursing_homes_nh_no_of_beds                VARCHAR,
    nursing_homes_nh_no_of_respite_beds        VARCHAR,
    residential_care_facilities_rcf_no_of_beds VARCHAR,
    rcf_respite_beds                           VARCHAR,
    single_entry_access_sea_participating      VARCHAR,
    x_coordinate                               VARCHAR,
    y_coordinate                               VARCHAR,
    location                                   VARCHAR,
    zone                                       VARCHAR,
    the_geom                                   VARCHAR,
    facility_id                                VARCHAR
);

-- Every bound in the build, named once and read from here. Nothing downstream
-- hard-codes a limit, a rounding depth, or a flag value.
CREATE OR REPLACE TABLE params AS
SELECT
    25  AS top_facility_limit,   -- rows in the top_facilities section
    2   AS round_dp,             -- decimals on every share, average, and median
    'Y' AS sea_yes_flag,         -- the value that counts as SEA participating
    145 AS snapshot_row_count;   -- committed snapshot size, checked in row_accounting

-- The four bed columns, named once.
--
-- total_beds = nursing + residential, that is, the two rows with is_core_bed = 1.
-- Respite beds are reported as their own bed types and are never folded into
-- total_beds: they are short-stay capacity, not standing places, and mixing them
-- into the headline would overstate the permanent bed supply.
CREATE OR REPLACE TABLE bed_type_dim (
    bed_type_ord  INTEGER,
    bed_type      VARCHAR,
    source_column VARCHAR,
    is_core_bed   INTEGER,
    bed_label     VARCHAR
);

INSERT INTO bed_type_dim VALUES
    (1, 'nursing',             'nursing_homes_nh_no_of_beds',                1, 'Nursing home beds'),
    (2, 'residential',         'residential_care_facilities_rcf_no_of_beds', 1, 'Residential care beds'),
    (3, 'nursing_respite',     'nursing_homes_nh_no_of_respite_beds',        0, 'Nursing home respite beds'),
    (4, 'residential_respite', 'rcf_respite_beds',                           0, 'Residential care respite beds');

-- The four health authority management zones the province publishes. A facility
-- whose zone is not one of these is excluded and counted, never quietly kept.
CREATE OR REPLACE TABLE zone_dim (
    zone_ord INTEGER,
    zone     VARCHAR
);

INSERT INTO zone_dim VALUES
    (1, 'Central'),
    (2, 'Eastern'),
    (3, 'Northern'),
    (4, 'Western');

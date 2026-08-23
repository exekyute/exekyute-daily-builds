-- 00_schema.sql
-- Raw landing table plus every named constant this pipeline depends on.
--
-- All source columns land as text. Typing and validation happen in
-- 02_transform.sql so a bad value is classified and counted there, never
-- coerced to NULL on the way in.

CREATE OR REPLACE TABLE raw_centres (
    region           VARCHAR,
    center_name      VARCHAR,
    street_address   VARCHAR,
    city_town        VARCHAR,
    postal_code      VARCHAR,
    phone            VARCHAR,
    email            VARCHAR,
    web              VARCHAR,
    x_coordinate     VARCHAR,
    y_coordinate     VARCHAR,
    location_1       VARCHAR,
    location_details VARCHAR,
    facebook         VARCHAR,
    twitter          VARCHAR
);

-- NAMED CONSTANT: REGION_UNIVERSE.
-- The complete Nova Scotia Works region set this build measures coverage
-- against. It is a frozen declaration, not a GROUP BY over the snapshot, so
-- region_coverage left joins onto it and a region carrying zero centres still
-- materializes as a row. See spec.md for where this list comes from and what
-- it can and cannot detect.
CREATE OR REPLACE TABLE const_region_universe (
    region_ord INTEGER,
    region     VARCHAR
);
INSERT INTO const_region_universe VALUES
    (1, 'Annapolis Valley'),
    (2, 'Cape Breton'),
    (3, 'HRM'),
    (4, 'Northern'),
    (5, 'South Shore');

-- NAMED CONSTANT: CONTACT_CHANNELS.
-- The four public contact channels scored for service completeness, in report
-- order. The completeness table is driven by this list, so a channel that no
-- centre carries still reports as a zero row instead of disappearing.
CREATE OR REPLACE TABLE const_contact_channel (
    channel_ord INTEGER,
    channel     VARCHAR
);
INSERT INTO const_contact_channel VALUES
    (1, 'email'),
    (2, 'web'),
    (3, 'facebook'),
    (4, 'twitter');

-- NAMED CONSTANTS: the scalar rules.
--   fsa_length   an FSA is the first three characters of a postal code
--   fsa_pattern  a valid FSA is letter, digit, letter
--   lat/lon box  the plausible Nova Scotia coordinate window, used to
--                classify coordinates rather than trust them blindly
CREATE OR REPLACE TABLE const_rules (
    fsa_length  INTEGER,
    fsa_pattern VARCHAR,
    lat_min     DOUBLE,
    lat_max     DOUBLE,
    lon_min     DOUBLE,
    lon_max     DOUBLE
);
INSERT INTO const_rules VALUES
    (3, '^[A-Z][0-9][A-Z]$', 43.0, 47.5, -67.0, -59.0);

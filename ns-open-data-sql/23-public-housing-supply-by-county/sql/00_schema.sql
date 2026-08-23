-- 00_schema.sql
-- Landing tables for the two committed snapshots, plus the named constants
-- the rest of the pipeline reads. Every source column lands as text so that a
-- value which will not cast is counted as an exclusion class in
-- 02_transform.sql instead of turning into a silent NULL at load time.

CREATE OR REPLACE TABLE raw_families (
    uid               VARCHAR,
    project_number    VARCHAR,
    civic_address     VARCHAR,
    community         VARCHAR,
    number_of_units   VARCHAR,
    pid               VARCHAR,
    housing_authority VARCHAR,
    county            VARCHAR,
    municipality      VARCHAR,
    x_coordina        VARCHAR,
    y_coordina        VARCHAR,
    location_1        VARCHAR
);

CREATE OR REPLACE TABLE raw_seniors (
    id                VARCHAR,
    property_project  VARCHAR,
    pid               VARCHAR,
    name              VARCHAR,
    address           VARCHAR,
    city              VARCHAR,
    postal_code       VARCHAR,
    number_of_floors  VARCHAR,
    residential_units VARCHAR,
    housing_authority VARCHAR,
    county            VARCHAR,
    elevator          VARCHAR,
    oil_heat          VARCHAR,
    electric_heat     VARCHAR,
    public_water      VARCHAR,
    well              VARCHAR,
    sewer             VARCHAR,
    onsite_septic     VARCHAR,
    municipality      VARCHAR,
    x_coordina        VARCHAR,
    y_coordina        VARCHAR,
    location          VARCHAR
);

-- NAMED CONSTANT 1: the program-type universe.
-- Two rows, one per source file. This table is the right-hand side of the
-- cross join that materializes the county grid, so a county with no rows in
-- one source still gets a zero cell instead of a missing cell.
CREATE OR REPLACE TABLE const_program_type (
    program_type  VARCHAR,
    program_order INTEGER
);
INSERT INTO const_program_type VALUES
    ('Families', 1),
    ('Seniors',  2);

-- NAMED CONSTANT 2: county spelling substitutions, raw to canonical.
-- Applied after the mechanical rule in 02_transform.sql (collapse runs of
-- spaces, drop a trailing ' County'). On the committed snapshot the two
-- sources spell all eighteen counties identically and the mechanical rule
-- covers everything, so this table is declared with no rows. The summary
-- section reports county_name_substitutions, which is how the zero is proven
-- from the output rather than asserted in prose. A later re-pull that splits
-- a county on spelling gets fixed here, in one place, and nowhere else.
CREATE OR REPLACE TABLE const_county_map (
    county_raw VARCHAR,
    county     VARCHAR
);

-- NAMED CONSTANT 3: housing authority spelling substitutions, raw to
-- canonical. The seniors file carries one Halifax property under
-- 'Metro Regional Housing Authority' and forty-two under
-- 'Metropolitan Regional Housing Authority'; they are the same authority
-- written two ways. The authority is carried on the BI mart, not on the
-- county result, so this substitution changes no headline number.
CREATE OR REPLACE TABLE const_authority_map (
    authority_raw     VARCHAR,
    housing_authority VARCHAR
);
INSERT INTO const_authority_map VALUES
    ('Metro Regional Housing Authority', 'Metropolitan Regional Housing Authority');

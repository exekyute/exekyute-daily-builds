-- 00_schema.sql
-- Question this step answers: what shape does the data take before any analysis runs?
-- Defines a staging table for the raw snapshot, a cleaned table, the two analysis
-- tables, and the row-level mart that Power BI reads. No rows are touched here;
-- this only declares structure.

CREATE OR REPLACE TABLE raw_coops (
    registry_id                VARCHAR,
    co_op_name                 VARCHAR,
    incorporation_year         VARCHAR,  -- source column name; the values are full dates
    address                    VARCHAR,
    town                       VARCHAR,
    province_state             VARCHAR,
    postal_code                VARCHAR,
    non_profit_n_for_profit_p  VARCHAR,
    type                       VARCHAR
);

CREATE OR REPLACE TABLE clean_coops (
    registry_id         VARCHAR,
    co_op_name          VARCHAR,
    town                VARCHAR,
    incorporation_date  DATE,
    incorporation_year  INTEGER,
    decade              VARCHAR,  -- '1930s' .. '2020s'
    org_form            VARCHAR,  -- 'Non-profit' or 'For-profit'
    is_nonprofit        BIGINT,   -- 1 or 0
    coop_type           VARCHAR,
    age_years           DOUBLE    -- as of the pull date declared in 02_transform.sql
);

CREATE OR REPLACE TABLE incorporations_by_year (
    incorporation_year  INTEGER,
    incorporated        BIGINT,
    nonprofit_count     BIGINT,
    forprofit_count     BIGINT
);

CREATE OR REPLACE TABLE cohort_longevity (
    decade               VARCHAR,
    survivors            BIGINT,
    registry_share_pct   DOUBLE,
    nonprofit_count      BIGINT,
    forprofit_count      BIGINT,
    nonprofit_share_pct  DOUBLE,
    peak_year            INTEGER,
    peak_count           BIGINT,
    oldest_age_years     DOUBLE
);

CREATE OR REPLACE TABLE mart_coop_longevity (
    registry_id         VARCHAR,
    co_op_name          VARCHAR,
    town                VARCHAR,
    incorporation_date  DATE,
    incorporation_year  INTEGER,
    decade              VARCHAR,
    org_form            VARCHAR,
    is_nonprofit        BIGINT,
    coop_type           VARCHAR,
    age_years           DOUBLE
);

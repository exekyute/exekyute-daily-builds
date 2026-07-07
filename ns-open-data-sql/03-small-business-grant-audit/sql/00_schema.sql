-- 00_schema.sql
-- Defines the tables the pipeline fills: the raw snapshot as published, and
-- the derived recipients table (one row per grant record that received at
-- least one grant). All raw columns stay text, matching the source CSV.

DROP TABLE IF EXISTS raw_grants;
CREATE TABLE raw_grants (
    year                            VARCHAR,  -- program year, text as published
    ns_small_business               VARCHAR,  -- organization name
    type_of_business                VARCHAR,  -- business classification
    received_small_business_impact  VARCHAR,  -- Impact Grant (SBIG), yes or no
    received_small_business         VARCHAR   -- Reopening and Support Grant (SBRSG), yes or no
);

DROP TABLE IF EXISTS recipients;
CREATE TABLE recipients (
    year              VARCHAR,
    type_of_business  VARCHAR,
    got_sbig          BOOLEAN,   -- received the Impact Grant
    got_sbrsg         BOOLEAN    -- received the Reopening and Support Grant
);

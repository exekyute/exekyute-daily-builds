-- 00_schema.sql
-- Question this step answers: what shape does the source data arrive in, before any cleaning?
-- Declares the staging table that the pinned CSV snapshot is loaded into. Nothing is computed
-- here; the loader in 01_load.sql fills this table verbatim from the snapshot.

DROP TABLE IF EXISTS raw_farm;
CREATE TABLE raw_farm (
    commodity                 VARCHAR,   -- commodity label as published; spellings vary by year
    fiscal_year               VARCHAR,   -- fiscal year as a string, for example '2015-2016'
    total_of_registered_farms BIGINT     -- registered farms for that commodity that year; may be null
);

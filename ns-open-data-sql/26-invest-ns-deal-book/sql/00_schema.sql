-- 00_schema.sql
-- Raw landing table for the committed snapshot. Every column lands as text so
-- the load never guesses a type. Typing happens in 02_transform.sql, where a
-- value that will not cast fails the run loudly instead of turning into NULL.

CREATE OR REPLACE TABLE raw_deals (
    object_id_                  VARCHAR,
    account_name                VARCHAR,
    nsbi_sector                 VARCHAR,
    deal_type                   VARCHAR,
    nsbi_financial_contribution VARCHAR,
    place_name                  VARCHAR,
    nsbi_county                 VARCHAR,
    postalcode                  VARCHAR,
    fiscal_year                 VARCHAR,
    longitude                   VARCHAR,
    latitude                    VARCHAR,
    geolocation                 VARCHAR
);

-- 00_schema.sql
-- Raw landing table for the committed snapshot, plus the named constants
-- every later rule refers to. All raw columns land as text so that a bad
-- value fails loudly in 02_transform.sql instead of turning into NULL here.

CREATE OR REPLACE TABLE raw_landings (
    year           VARCHAR,
    port           VARCHAR,
    county         VARCHAR,
    kgs            VARCHAR,
    purchase_total VARCHAR
);

-- Named constants. Every threshold and marker used anywhere in the pipeline
-- is declared here and referenced by name, never re-typed inline.
--
--   county_total_prefix   Marks a published county aggregate row. The source
--                         mixes two grains in one table: port rows and one
--                         'Total for <County> County' row per county per year.
--                         Those aggregate rows are a different grain and would
--                         double count, so they are excluded from every port,
--                         county, and year sum and reported as their own class.
--   residual_port_label   The catch-all bucket the province publishes per
--                         county per year for landings not attributed to a
--                         named port. Kept in every sum (the dollars are real)
--                         and flagged so it can be told apart from a real port.
--   top_ports_n           How deep the Pareto section runs in the golden file.
--   min_kgs_for_price     Price per kg is computed only where kilograms are
--                         strictly greater than this, so the division is never
--                         by zero and never by NULL.
CREATE OR REPLACE TABLE constants AS
SELECT
    'Total for '             AS county_total_prefix,
    'Other'                  AS residual_port_label,
    25                       AS top_ports_n,
    CAST(0 AS DECIMAL(18,2)) AS min_kgs_for_price;

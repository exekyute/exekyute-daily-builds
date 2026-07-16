-- 01_load.sql
-- Load the pinned snapshot as text. All typing happens in 02_transform,
-- so a bad value in the source can never abort the load. The glob keeps
-- the dated filename out of the SQL.

CREATE TABLE raw_rates AS
SELECT *
FROM read_csv('data/raw/ns_property-tax-rates_*.csv', header = true, all_varchar = true);

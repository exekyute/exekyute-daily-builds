-- 00_schema.sql
-- Reset the working tables. Every run rebuilds from the pinned snapshot,
-- so nothing here carries state between runs.

DROP TABLE IF EXISTS raw_rates;
DROP TABLE IF EXISTS rates_clean;
DROP TABLE IF EXISTS tax_burden_index;

-- 02_transform.sql
-- Question: for each municipality in each fiscal year, what is the operating surplus?
--
-- Operating surplus is defined as total operating revenue minus total operating
-- expenditure, so it is derived here from total_revenues and total_expenditures
-- rather than read from the dataset's own operating_surplus column. Those two
-- source columns are whole dollars; casting to DECIMAL(18,2) keeps the money to
-- the cent and makes the subtraction tie exactly.
--
-- Municipality identity is (region, region_type), not region alone: several names
-- (Antigonish, Lunenburg, Yarmouth, Digby, Shelburne) belong to both a Town and a
-- separate Rural Municipality, which are different governments that share a name.
--
-- Rows with a missing total (revenue or expenditure absent) cannot yield a
-- surplus and are dropped here.

CREATE VIEW municipal_operating AS
SELECT
  year,
  region,
  region_type,
  CAST(total_revenues     AS DECIMAL(18, 2)) AS total_revenues,
  CAST(total_expenditures AS DECIMAL(18, 2)) AS total_expenditures,
  CAST(total_revenues     AS DECIMAL(18, 2))
    - CAST(total_expenditures AS DECIMAL(18, 2))     AS operating_surplus
FROM raw_operating_fund
WHERE NULLIF(TRIM(total_revenues),     '') IS NOT NULL
  AND NULLIF(TRIM(total_expenditures), '') IS NOT NULL;

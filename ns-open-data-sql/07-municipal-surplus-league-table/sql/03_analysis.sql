-- 03_analysis.sql
-- Question: ranked within each year and tracked over time, who runs the largest
-- operating surpluses and deficits, and how does each municipality move year over year?
--
--   surplus_rank_in_year   1 = largest surplus that fiscal year (RANK, ties share a place)
--   deficit_rank_in_year   1 = largest deficit that fiscal year (most negative surplus)
--   municipalities_in_year how many municipalities the rank is out of that year
--   prior_year_surplus     the same municipality's surplus in the previous fiscal year (LAG)
--   yoy_surplus_change     this year's surplus minus prior_year_surplus (NULL in a first year)
--   years_observed         how many fiscal years this municipality appears with a surplus
--   mean_surplus           its average operating surplus across those years (trend baseline)
--
-- Year-over-year and the trend baseline partition by (region, region_type) so a Town
-- is never compared against the Rural Municipality of the same name. The fiscal-year
-- label sorts chronologically as text (2013-14 < 2014-15 < ... < 2023-24), so it
-- doubles as the LAG ordering key.

CREATE VIEW surplus_league AS
SELECT
  year,
  region,
  region_type,
  total_revenues,
  total_expenditures,
  operating_surplus,
  RANK() OVER (PARTITION BY year ORDER BY operating_surplus DESC) AS surplus_rank_in_year,
  RANK() OVER (PARTITION BY year ORDER BY operating_surplus ASC)  AS deficit_rank_in_year,
  CAST(COUNT(*) OVER (PARTITION BY year) AS INTEGER)             AS municipalities_in_year,
  LAG(operating_surplus) OVER w                                  AS prior_year_surplus,
  CAST(operating_surplus - LAG(operating_surplus) OVER w AS DECIMAL(18, 2)) AS yoy_surplus_change,
  CAST(COUNT(*) OVER (PARTITION BY region, region_type) AS INTEGER) AS years_observed,
  CAST(ROUND(AVG(operating_surplus) OVER (PARTITION BY region, region_type), 2) AS DECIMAL(18, 2)) AS mean_surplus
FROM municipal_operating
WINDOW w AS (PARTITION BY region, region_type ORDER BY year);

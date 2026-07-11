-- 99_export.sql
-- Question: write the league table to a stable CSV that can be diffed against the golden copy.
--
-- Ordering is fixed so the output is byte-for-byte reproducible: latest fiscal year
-- first, then largest surplus to largest deficit, with (region, region_type) as the
-- final tie-break. That puts the headline (biggest surplus at the top of the newest
-- year, biggest deficit at the bottom of that block) at the top of the file.

COPY (
  SELECT
    year,
    region,
    region_type,
    total_revenues,
    total_expenditures,
    operating_surplus,
    surplus_rank_in_year,
    deficit_rank_in_year,
    municipalities_in_year,
    prior_year_surplus,
    yoy_surplus_change,
    years_observed,
    mean_surplus
  FROM surplus_league
  ORDER BY year DESC, operating_surplus DESC, region ASC, region_type ASC
) TO 'out/surplus_league.csv' (HEADER, DELIMITER ',');

-- 99_export.sql
-- Write the analysis table twice: once to out/ for the golden diff, once to
-- the BI mart that Power BI and the dashboard read. The fixed ORDER BY is
-- what makes the golden diff reproducible.

COPY (
    SELECT
        area, area_type, year_label, year_start,
        residential_rate, commercial_rate, spread,
        rank_in_year, yoy_spread_change, is_outlier
    FROM tax_burden_index
    ORDER BY year_start, rank_in_year, area, area_type
) TO 'out/tax_burden_index.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        area, area_type, year_label, year_start,
        residential_rate, commercial_rate, spread,
        rank_in_year, yoy_spread_change, is_outlier
    FROM tax_burden_index
    ORDER BY year_start, rank_in_year, area, area_type
) TO 'bi/exports/mart_tax_burden.csv' (HEADER, DELIMITER ',');

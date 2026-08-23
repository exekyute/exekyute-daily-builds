-- 99_export.sql
-- Write the golden result and the BI mart. Both ORDER BY clauses are total
-- orders that end in site then fiscal_year_start, so the byte content of these
-- files does not depend on the engine or the version.

COPY (
    SELECT
        section, rank, measure,
        fiscal_year, fiscal_year_start, zone, facility_type, site,
        site_years, zero_site_years,
        total_hours, temporary_hours, scheduled_hours, temporary_share_pct,
        yoy_change_hours, yoy_change_pct
    FROM ed_closures
    ORDER BY section_order, rank, measure, zone, facility_type,
             site, fiscal_year_start
) TO 'out/ed_closures.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        fiscal_year, fiscal_year_start, zone, facility_type, site,
        temporary_hours, scheduled_hours, total_hours, is_zero_closure
    FROM mart_ed_closures
    ORDER BY zone, facility_type, site, fiscal_year_start
) TO 'out/mart_ed_closures.csv' (HEADER, DELIMITER ',');

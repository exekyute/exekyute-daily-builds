-- 99_export.sql
-- Write the land accounting result and the BI mart. Both carry a total
-- ORDER BY ending in a unique term, so the files are byte-stable run to run.

COPY (
    SELECT
        section, rank, measure, designation, authority, owner, status,
        area_name, records, hectares, share_pct,
        cumulative_hectares, cumulative_share_pct
    FROM protected_areas
    ORDER BY section_order, rank
) TO 'out/protected_areas.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        objectid, area_name, designation, authority, owner, status,
        hectares, designation_year, record_rank
    FROM mart_protected
    ORDER BY record_rank
) TO 'out/mart_protected.csv' (HEADER, DELIMITER ',');

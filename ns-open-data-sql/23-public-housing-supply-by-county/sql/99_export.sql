-- 99_export.sql
-- Write the result and the BI mart. Both ORDER BY clauses are total orders
-- ending in unique tie-breakers, so the files are byte-stable run to run and
-- across DuckDB versions.

COPY (
    SELECT
        section, rank, measure, county, program_type,
        properties, units, share_pct, value
    FROM housing_supply
    ORDER BY section_order, rank, county, program_type
) TO 'out/housing_supply.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        program_type, source_id, county, municipality, community,
        property_label, housing_authority, units, latitude, longitude
    FROM mart_housing
    ORDER BY county, program_type, source_id
) TO 'out/mart_housing.csv' (HEADER, DELIMITER ',');

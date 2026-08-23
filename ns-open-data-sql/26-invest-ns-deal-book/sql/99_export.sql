-- 99_export.sql
-- Write the deal book, the BI mart, and the dashboard cube. Each COPY carries
-- an explicit total ORDER BY ending in a unique tie-breaker, so the files are
-- byte-stable run to run and across DuckDB versions.

COPY (
    SELECT
        section, rank, measure, fiscal_year, nsbi_sector, nsbi_county,
        deal_type, account_name, deals, amount, share_pct, yoy_change, yoy_pct
    FROM deal_book
    ORDER BY section_order, rank
) TO 'out/deal_book.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        object_id, fiscal_year, fiscal_year_start, nsbi_sector, nsbi_county,
        county_is_geographic, deal_type, account_name, place_name, postalcode,
        nsbi_financial_contribution, has_contribution, latitude, longitude,
        is_mappable, in_ns_bounds
    FROM mart_deal_book
    ORDER BY object_id
) TO 'out/mart_deal_book.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        fiscal_year, fiscal_year_start, nsbi_sector, nsbi_county,
        county_is_geographic, deal_type, deals, funded_deals, blank_deals,
        zero_deals, mappable_deals, in_bounds_deals, contribution
    FROM dash_deal_book
    ORDER BY fiscal_year_start, nsbi_sector, nsbi_county, deal_type
) TO 'out/dash_deal_book.csv' (HEADER, DELIMITER ',');

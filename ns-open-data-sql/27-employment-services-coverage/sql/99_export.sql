-- 99_export.sql
-- Write the golden result and the BI mart. Both carry a total ORDER BY whose
-- last term is unique, so the files are byte-stable run to run.
--   services_coverage: (section_order, rank) is already unique by construction;
--                      the trailing terms are belt and braces.
--   mart_services:     (region, center_name, city_town, street_address) is
--                      unique across all 47 rows. Region and centre name alone
--                      are not: one provider runs up to nine sites, and one
--                      town holds two sites of the same provider.

COPY (
    SELECT
        section, rank, measure, region, city_town, fsa,
        centres, towns, providers, share_pct
    FROM services_coverage
    ORDER BY section_order, rank, region, city_town, fsa, measure
) TO 'out/services_coverage.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        region, center_name, city_town, street_address, postal_code, fsa,
        latitude, longitude, phone, email, web, facebook, twitter,
        has_email, has_web, has_facebook, has_twitter, contact_channels,
        region_centres, region_share_pct
    FROM mart_services
    ORDER BY region, center_name, city_town, street_address
) TO 'out/mart_services.csv' (HEADER, DELIMITER ',');

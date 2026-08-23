-- 01_load.sql
-- Load the pinned snapshot. The filename carries the pull date; swapping in a
-- newer snapshot means re-baselining expected/deal_book.csv on purpose.

INSERT INTO raw_deals
SELECT
    object_id_, account_name, nsbi_sector, deal_type,
    nsbi_financial_contribution, place_name, nsbi_county, postalcode,
    fiscal_year, longitude, latitude, geolocation
FROM read_csv(
    'data/raw/ns_invest-ns-financial-programs_2026-07-25.csv',
    header = true,
    all_varchar = true
);

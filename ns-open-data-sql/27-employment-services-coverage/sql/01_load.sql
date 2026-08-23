-- 01_load.sql
-- Load the pinned snapshot. The filename carries the pull date; replacing the
-- snapshot means re-baselining expected/services_coverage.csv on purpose.

INSERT INTO raw_centres
SELECT
    region, center_name, street_address, city_town, postal_code, phone,
    email, web, x_coordinate, y_coordinate, location_1, location_details,
    facebook, twitter
FROM read_csv(
    'data/raw/ns_nsworks-centres_2026-07-25.csv',
    header = true,
    all_varchar = true
);

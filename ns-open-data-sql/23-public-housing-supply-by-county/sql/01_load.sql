-- 01_load.sql
-- Load both pinned snapshots. The filenames carry the pull date; replacing a
-- snapshot means re-baselining expected/housing_supply.csv on purpose.

INSERT INTO raw_families
SELECT
    uid, project_number, civic_address, community, number_of_units, pid,
    housing_authority, county, municipality, x_coordina, y_coordina, location_1
FROM read_csv(
    'data/raw/ns_public-housing-families_2026-07-25.csv',
    header = true,
    all_varchar = true
);

INSERT INTO raw_seniors
SELECT
    id, property_project, pid, name, address, city, postal_code,
    number_of_floors, residential_units, housing_authority, county,
    elevator, oil_heat, electric_heat, public_water, well, sewer,
    onsite_septic, municipality, x_coordina, y_coordina, location
FROM read_csv(
    'data/raw/ns_public-housing-seniors_2026-07-25.csv',
    header = true,
    all_varchar = true
);

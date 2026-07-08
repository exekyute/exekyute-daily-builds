-- Load the pinned snapshot into the raw staging table.
-- The file under data/raw is a committed, dated copy of the Socrata export, so
-- the same rows load every run. Everything comes in as text (all_varchar); the
-- typing happens in the next step.

INSERT INTO stocking_raw
SELECT
    county, name, type, easting, northing,
    primary_stocking_objective, secondary_stocking_objective,
    number_released, stocking_date, growth_stage, mark, hatchery,
    fish_length_cm, fish_weight_g, stock, stock_strain
FROM read_csv_auto(
    'data/raw/ns_hatchery-stocking_2026-07-05.csv',
    header = true,
    all_varchar = true
);

-- Export the summary as the single deterministic result file.
-- The column list is fixed and the ORDER BY is repeated so the CSV row order
-- does not depend on how the table happened to be built.

COPY (
    SELECT
        county,
        waterbody,
        waterbody_type,
        species,
        stocking_year,
        stocking_events,
        fish_released,
        avg_length_cm,
        avg_weight_g
    FROM stocking_summary
    ORDER BY county, waterbody, waterbody_type, species, stocking_year
) TO 'out/stocking_summary.csv' (HEADER, DELIMITER ',');

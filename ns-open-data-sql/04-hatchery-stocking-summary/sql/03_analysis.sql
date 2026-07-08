-- Question answered: for each county, waterbody, species, and year, how many
-- stocking events took place, how many fish were released, and what was the
-- average size at release?
--
-- The grain is one row per (county, waterbody, waterbody type, species, year),
-- so the five grouping columns together identify each row.
--   - stocking_events is the effort measure: the count of stocking records.
--     Summing it by year gives the effort trend over time.
--   - fish_released summed by species or by waterbody gives the totals behind
--     the headline (which species and which water were stocked most).
--   - avg_length_cm and avg_weight_g describe the average size at release, and
--     are left blank for a group that has no measured length or weight.
--
-- The ORDER BY makes the built table deterministic; 99_export repeats it so the
-- exported file does not rely on table order.

DROP TABLE IF EXISTS stocking_summary;
CREATE TABLE stocking_summary AS
SELECT
    county,
    waterbody,
    waterbody_type,
    species,
    stocking_year,
    count(*)                      AS stocking_events,
    sum(number_released)          AS fish_released,
    round(avg(fish_length_cm), 2) AS avg_length_cm,
    round(avg(fish_weight_g), 2)  AS avg_weight_g
FROM stocking_fact
GROUP BY county, waterbody, waterbody_type, species, stocking_year
ORDER BY county, waterbody, waterbody_type, species, stocking_year;

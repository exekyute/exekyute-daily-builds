-- Clean and type the raw rows into the analysis fact table.
--
-- Cleaning rules, each here on purpose:
--   1. Trim whitespace from the text fields. One species value carries a
--      trailing space ("Atlantic Salmon "), which would otherwise split the
--      species into two groups.
--   2. Read the calendar year from the first four characters of the ISO
--      stocking_date. Every date in the snapshot parses cleanly.
--   3. Cast the released count to a whole number. A handful of records show
--      zero fish released; they stay in as valid events that add nothing to the
--      fish totals.
--   4. Keep length and weight as measured, but treat a zero or missing value as
--      "not recorded" (NULL) rather than a real measurement, so it does not pull
--      the average size at release toward zero.

INSERT INTO stocking_fact
SELECT
    trim(county)                                   AS county,
    trim(name)                                     AS waterbody,
    trim(type)                                     AS waterbody_type,
    trim(stock)                                    AS species,
    CAST(substr(stocking_date, 1, 4) AS INTEGER)   AS stocking_year,
    CAST(number_released AS BIGINT)                AS number_released,
    CASE WHEN CAST(fish_length_cm AS DOUBLE) > 0
         THEN CAST(fish_length_cm AS DOUBLE) END   AS fish_length_cm,
    CASE WHEN CAST(fish_weight_g AS DOUBLE) > 0
         THEN CAST(fish_weight_g AS DOUBLE) END    AS fish_weight_g
FROM stocking_raw;

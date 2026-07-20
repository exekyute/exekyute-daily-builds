-- 02_transform: type the raw text and keep only usable rows.
-- Rules, in order (see spec.md):
--   1. FSA = first three postal characters, uppercased and trimmed, and it
--      must match letter-digit-letter. Drops blanks, the literal 'NS', and
--      malformed codes like 'B36' or 'BOK'.
--   2. year_installed must cast to an integer.
--   3. total_dc_capacity_kw must cast to a number greater than zero.

CREATE OR REPLACE TABLE solar_clean AS
SELECT
    UPPER(TRIM(partial_postal_code))          AS fsa,
    CAST(year_installed AS INTEGER)           AS year,
    CAST(total_dc_capacity_kw AS DOUBLE)      AS kw
FROM solar_raw
WHERE partial_postal_code IS NOT NULL
  AND regexp_matches(UPPER(TRIM(partial_postal_code)), '^[A-Z][0-9][A-Z]$')
  AND TRY_CAST(year_installed AS INTEGER) IS NOT NULL
  AND TRY_CAST(total_dc_capacity_kw AS DOUBLE) > 0;

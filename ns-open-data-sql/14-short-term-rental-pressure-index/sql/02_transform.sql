-- 02_transform.sql
-- Question this step answers: what does each census division's registry look like as
-- clean long-format rows, and does the source's own Total row agree with the parts?
--
-- Cleaning rules:
--   region   : census_division trimmed, with the trailing ' CD' suffix removed, so
--              'Halifax CD' becomes 'Halifax'. The names then match Nova Scotia's
--              county names, which is also what lets Tableau geocode them.
--   Total row: the source ships a 'Total' rollup row. It is excluded from the
--              regions, but not ignored: the check below compares it to the sum of
--              the 18 division rows, category by category, and the CHECK constraint
--              on check_totals aborts the whole run if they disagree.
--   counts   : the three category columns are cast from text to BIGINT.
--
-- The wide source (one column per category) is unpivoted to one row per
-- (region, category), which is the shape the analysis groups over.

-- cross-check: the division rows must sum to the source's own Total row
INSERT INTO check_totals
SELECT
        sum(CASE WHEN trim(census_division) <> 'Total'
                 THEN CAST(commercial_short_term_rental AS BIGINT) END)
      = max(CASE WHEN trim(census_division) = 'Total'
                 THEN CAST(commercial_short_term_rental AS BIGINT) END)
    AND sum(CASE WHEN trim(census_division) <> 'Total'
                 THEN CAST(whole_home_primary_residence AS BIGINT) END)
      = max(CASE WHEN trim(census_division) = 'Total'
                 THEN CAST(whole_home_primary_residence AS BIGINT) END)
    AND sum(CASE WHEN trim(census_division) <> 'Total'
                 THEN CAST(traditional_tourist_accommodation AS BIGINT) END)
      = max(CASE WHEN trim(census_division) = 'Total'
                 THEN CAST(traditional_tourist_accommodation AS BIGINT) END)
FROM raw_registry;

INSERT INTO clean_registrations
WITH divisions AS (
    SELECT
        regexp_replace(trim(census_division), ' CD$', '') AS region,
        CAST(commercial_short_term_rental      AS BIGINT) AS commercial_short_term_rental,
        CAST(whole_home_primary_residence      AS BIGINT) AS whole_home_primary_residence,
        CAST(traditional_tourist_accommodation AS BIGINT) AS traditional_tourist_accommodation
    FROM raw_registry
    WHERE trim(census_division) <> 'Total'
)
SELECT region, 'commercial short-term rental' AS category,
       commercial_short_term_rental AS registrations
FROM divisions
UNION ALL
SELECT region, 'whole-home primary residence' AS category,
       whole_home_primary_residence AS registrations
FROM divisions
UNION ALL
SELECT region, 'traditional tourist accommodation' AS category,
       traditional_tourist_accommodation AS registrations
FROM divisions;

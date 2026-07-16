-- 02_transform: type the raw text and normalize it into the mart grain, one
-- row per tree. No rows are dropped: TREEID is unique and every tree is a real
-- asset, so unusable attribute values are labelled ('Unidentified', 'Unknown')
-- rather than filtered, which keeps the mart total equal to the raw row count.
--
-- Field notes grounded in the live data (see SOURCE.md and data_dictionary.md):
--   * SP_COMM arrives already in title case; cleaning is a trim plus an internal
--     whitespace collapse. Blank names and the literal 'Unknown Species' are
--     folded into a single 'Unidentified' bucket.
--   * DBH stores an integer size-class code 1..9, not a centimetre measurement,
--     despite the source unit label 'CM'. It is bucketed into ordered tiers.
--   * The dataset carries no tree-condition or health rating (CONDITPERD is
--     empty for every row), so the categorical dimensions are the two real
--     attributes the data does record: general location (LOCGEN) and whether
--     overhead wires are present (WIRES).
--   * INSTYR is only populated and plausible for a minority of trees; values
--     outside 1900..2026 (mostly 0 and blanks) become a null install year.

CREATE OR REPLACE TABLE trees_clean AS
SELECT
    TRIM(TREEID) AS tree_id,

    CASE
        WHEN SP_COMM IS NULL OR TRIM(SP_COMM) IN ('', 'Unknown Species')
            THEN 'Unidentified'
        ELSE regexp_replace(TRIM(SP_COMM), '\s+', ' ', 'g')
    END AS species_common,

    -- Scientific names are normalized to binomial case: genus capitalized, the
    -- rest lowercased. This reconciles the source's inconsistent casing (it
    -- stores 'Acer Platanoides' for Norway Maple next to a correct
    -- 'Acer rubrum' for Red Maple) into one canonical spelling per taxon.
    CASE
        WHEN SP_SCIEN IS NULL OR TRIM(SP_SCIEN) IN ('', 'Unknown Species')
            THEN 'Unknown'
        ELSE UPPER(LEFT(regexp_replace(TRIM(SP_SCIEN), '\s+', ' ', 'g'), 1))
             || LOWER(SUBSTR(regexp_replace(TRIM(SP_SCIEN), '\s+', ' ', 'g'), 2))
    END AS species_scientific,

    TRY_CAST(DBH AS INTEGER) AS dbh,

    CASE
        WHEN TRY_CAST(DBH AS INTEGER) BETWEEN 1 AND 2 THEN 'Class 1-2'
        WHEN TRY_CAST(DBH AS INTEGER) BETWEEN 3 AND 4 THEN 'Class 3-4'
        WHEN TRY_CAST(DBH AS INTEGER) BETWEEN 5 AND 6 THEN 'Class 5-6'
        WHEN TRY_CAST(DBH AS INTEGER) BETWEEN 7 AND 9 THEN 'Class 7-9'
        ELSE 'Unknown'
    END AS dbh_class,

    CASE UPPER(TRIM(COALESCE(LOCGEN, '')))
        WHEN 'ROW' THEN 'Street right-of-way'
        WHEN 'OSP' THEN 'Open space'
        ELSE 'Unknown'
    END AS setting,

    CASE UPPER(TRIM(COALESCE(WIRES, '')))
        WHEN 'Y' THEN 'Under wires'
        WHEN 'N' THEN 'Clear of wires'
        ELSE 'Unknown'
    END AS wires,

    CASE
        WHEN TRY_CAST(INSTYR AS INTEGER) BETWEEN 1900 AND 2026
            THEN TRY_CAST(INSTYR AS INTEGER)
    END AS install_year,

    CASE
        WHEN UPPER(TRIM(COALESCE(OWNER, ''))) = 'HRM' THEN 'HRM'
        ELSE 'Unknown'
    END AS owner,

    CASE UPPER(TRIM(COALESCE(ASSETSTAT, '')))
        WHEN 'INS' THEN 'Installed'
        ELSE 'Unknown'
    END AS status,

    CAST(ROUND(TRY_CAST(LAT AS DOUBLE), 6) AS DECIMAL(9, 6)) AS lat,
    CAST(ROUND(TRY_CAST(LON AS DOUBLE), 6) AS DECIMAL(9, 6)) AS lon
FROM trees_raw;

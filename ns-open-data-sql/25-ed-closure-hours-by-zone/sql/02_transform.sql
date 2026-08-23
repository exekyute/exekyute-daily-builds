-- 02_transform.sql
-- Validate, type, and canonicalize. No row is silently dropped: every raw row
-- is tagged with either NULL (kept) or one named exclusion reason, and
-- row_accounting counts each class so the totals always add back to 456.

-- Step 1: tag every raw row. The CASE arms are checked in order, so a row that
-- fails two checks is reported under the first one listed. That keeps the
-- accounting stable no matter what a future snapshot contains.
CREATE OR REPLACE TABLE tagged_closures AS
SELECT
    raw.year                                         AS fiscal_year_raw,
    trim(raw.zone)                                   AS zone,
    trim(raw.type)                                   AS facility_type,
    canonical_site(raw.site)                         AS site_punctuation_fixed,
    raw.temporary                                    AS temporary_raw,
    raw.scheduled                                    AS scheduled_raw,
    raw.total                                        AS total_raw,
    CASE
        WHEN raw.year IS NULL
             OR NOT regexp_matches(raw.year,
                    (SELECT rule_value FROM rule_constants
                     WHERE rule_name = 'fiscal_year_pattern'))
            THEN 'unparsable_fiscal_year'
        WHEN raw.temporary IS NULL OR raw.scheduled IS NULL OR raw.total IS NULL
             OR NOT regexp_matches(raw.temporary,
                    (SELECT rule_value FROM rule_constants
                     WHERE rule_name = 'hours_pattern'))
             OR NOT regexp_matches(raw.scheduled,
                    (SELECT rule_value FROM rule_constants
                     WHERE rule_name = 'hours_pattern'))
             OR NOT regexp_matches(raw.total,
                    (SELECT rule_value FROM rule_constants
                     WHERE rule_name = 'hours_pattern'))
            THEN 'unparsable_hours'
        WHEN canonical_site(raw.site) IS NULL OR canonical_site(raw.site) = ''
            THEN 'missing_site'
        WHEN trim(raw.zone) IS NULL OR trim(raw.zone) = ''
             OR trim(raw.type) IS NULL OR trim(raw.type) = ''
            THEN 'missing_zone_or_type'
        ELSE NULL
    END                                              AS exclusion_reason
FROM raw_closures AS raw;

-- Step 2: keep the tagged-clean rows, apply the explicit rename map, and cast.
-- Hours land as DECIMAL(18,1) because the portal reports one decimal place;
-- decimal keeps the sums exact instead of drifting the way a float would.
CREATE OR REPLACE TABLE clean_closures AS
SELECT
    t.fiscal_year_raw                                AS fiscal_year,
    fiscal_year_start(t.fiscal_year_raw)             AS fiscal_year_start,
    t.zone                                           AS zone,
    t.facility_type                                  AS facility_type,
    COALESCE(rn.canonical_site, t.site_punctuation_fixed) AS site,
    CAST(t.temporary_raw AS DECIMAL(18,1))           AS temporary_hours,
    CAST(t.scheduled_raw AS DECIMAL(18,1))           AS scheduled_hours,
    CAST(t.total_raw     AS DECIMAL(18,1))           AS total_hours
FROM tagged_closures AS t
LEFT JOIN rule_site_rename AS rn
       ON rn.raw_site = t.site_punctuation_fixed
WHERE t.exclusion_reason IS NULL;

-- Step 3: the row ledger. Snapshot rows minus each exclusion class equals the
-- clean row count, and that identity is exported so it can be read off the
-- golden file rather than taken on trust.
CREATE OR REPLACE TABLE row_accounting AS
SELECT 1 AS ord, 'rows_in_snapshot' AS measure,
       (SELECT count(*) FROM raw_closures) AS row_count
UNION ALL SELECT 2, 'rows_excluded_unparsable_fiscal_year',
       (SELECT count(*) FROM tagged_closures WHERE exclusion_reason = 'unparsable_fiscal_year')
UNION ALL SELECT 3, 'rows_excluded_unparsable_hours',
       (SELECT count(*) FROM tagged_closures WHERE exclusion_reason = 'unparsable_hours')
UNION ALL SELECT 4, 'rows_excluded_missing_site',
       (SELECT count(*) FROM tagged_closures WHERE exclusion_reason = 'missing_site')
UNION ALL SELECT 5, 'rows_excluded_missing_zone_or_type',
       (SELECT count(*) FROM tagged_closures WHERE exclusion_reason = 'missing_zone_or_type')
UNION ALL SELECT 6, 'rows_loaded_clean',
       (SELECT count(*) FROM clean_closures);

-- Step 4: one row per site, carrying the zone and facility type as reported in
-- that site's most recent observed fiscal year. Eight sites were reclassified
-- part way through the window (see spec.md), so the site-level ranking needs a
-- single stated type and "most recent" is the only choice that does not depend
-- on scan order. Site and fiscal year are unique together, so the ordering
-- picks exactly one row.
CREATE OR REPLACE TABLE site_profile AS
SELECT
    site,
    zone,
    facility_type            AS facility_type_latest,
    latest_fiscal_year_start
FROM (
    SELECT
        site,
        zone,
        facility_type,
        max(fiscal_year_start) OVER (PARTITION BY site) AS latest_fiscal_year_start,
        row_number() OVER (
            PARTITION BY site
            ORDER BY fiscal_year_start DESC, facility_type, zone
        ) AS pick
    FROM clean_closures
)
WHERE pick = 1;

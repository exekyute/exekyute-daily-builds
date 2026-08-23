-- 02_transform.sql
-- Stack the two sources into one long table and normalize the columns that
-- differ between them. Rules, all deterministic:
--   * program_type is the source label: 'Families' or 'Seniors'. It is the
--     only thing that says which file a row came from once the two are
--     stacked, so every downstream total can be split back apart.
--   * units: families call the column number_of_units, seniors call it
--     residential_units. Both become the single integer column `units`.
--   * county: collapse runs of spaces, drop a trailing ' County', then apply
--     const_county_map. A row whose county is blank after that is excluded
--     and counted, never dropped in silence.
--   * housing_authority: collapse runs of spaces, then apply
--     const_authority_map.
--   * coordinates: in both files x_coordina is LONGITUDE and y_coordina is
--     LATITUDE, which is the reverse of the column-name reading. They are
--     carried on the BI mart only; no county figure depends on them.
--   * community: the families file calls it community, the seniors file
--     calls it city. Same idea, one column.

CREATE OR REPLACE TABLE stacked_raw AS
SELECT
    'Families'              AS program_type,
    trim(uid)               AS source_id,
    trim(civic_address)     AS property_label,
    trim(community)         AS community,
    trim(municipality)      AS municipality,
    trim(housing_authority) AS authority_source,
    trim(county)            AS county_source,
    trim(number_of_units)   AS units_source,
    trim(y_coordina)        AS latitude_source,
    trim(x_coordina)        AS longitude_source
FROM raw_families
UNION ALL
SELECT
    'Seniors',
    trim(id),
    trim(name),
    trim(city),
    trim(municipality),
    trim(housing_authority),
    trim(county),
    trim(residential_units),
    trim(y_coordina),
    trim(x_coordina)
FROM raw_seniors;

-- Mechanical normalization first, then the declared substitution maps. Both
-- substitution flags are kept on the row so the summary can report how many
-- times each map actually fired.
CREATE OR REPLACE TABLE stacked_norm AS
WITH mechanical AS (
    SELECT
        s.*,
        regexp_replace(
            regexp_replace(s.county_source, ' +', ' ', 'g'),
            ' County$', '', ''
        ) AS county_mech,
        regexp_replace(s.authority_source, ' +', ' ', 'g') AS authority_mech,
        TRY_CAST(s.units_source AS INTEGER)                AS units_cast,
        TRY_CAST(s.latitude_source AS DOUBLE)              AS latitude,
        TRY_CAST(s.longitude_source AS DOUBLE)             AS longitude
    FROM stacked_raw s
)
SELECT
    m.program_type,
    m.source_id,
    m.property_label,
    m.community,
    m.municipality,
    COALESCE(am.housing_authority, m.authority_mech)        AS housing_authority,
    CASE WHEN am.housing_authority IS NOT NULL THEN 1 ELSE 0 END AS authority_substituted,
    COALESCE(cm.county, m.county_mech)                      AS county,
    CASE WHEN cm.county IS NOT NULL THEN 1 ELSE 0 END       AS county_substituted,
    m.county_source,
    m.units_source,
    m.units_cast,
    m.latitude,
    m.longitude,
    CASE
        WHEN COALESCE(cm.county, m.county_mech, '') = '' THEN 'county_blank'
        WHEN m.units_cast IS NULL                       THEN 'units_not_a_number'
        WHEN m.units_cast < 1                           THEN 'units_not_positive'
        ELSE ''
    END AS exclusion_reason
FROM mechanical m
LEFT JOIN const_county_map    cm ON cm.county_raw    = m.county_mech
LEFT JOIN const_authority_map am ON am.authority_raw = m.authority_mech;

-- The kept rows. One row per listed property record: a civic address in the
-- families file, a named building in the seniors file.
CREATE OR REPLACE TABLE housing_long AS
SELECT
    program_type,
    source_id,
    property_label,
    community,
    municipality,
    housing_authority,
    county,
    units_cast AS units,
    latitude,
    longitude
FROM stacked_norm
WHERE exclusion_reason = '';

-- The excluded rows, kept as a table so every exclusion class can be counted
-- and reported in the result rather than vanishing between two steps.
CREATE OR REPLACE TABLE excluded_rows AS
SELECT
    program_type,
    source_id,
    county_source,
    units_source,
    exclusion_reason
FROM stacked_norm
WHERE exclusion_reason <> '';

-- THE COUNTY UNIVERSE. Coverage gaps are only defined against a declared
-- universe, and this build declares it as the distinct normalized counties
-- present in the kept rows of either source. Nothing external is consulted,
-- so a county that appears in neither source cannot appear in the result.
CREATE OR REPLACE TABLE county_universe AS
SELECT DISTINCT county FROM housing_long;

-- The grid: every county in the universe against both program types. The
-- cross join is what materializes a zero cell where a county has rows in one
-- source and none in the other. Without it that cell would simply be missing
-- from the output, which reads as "no answer" rather than "zero".
CREATE OR REPLACE TABLE county_grid AS
SELECT
    u.county,
    p.program_type,
    p.program_order
FROM county_universe u
CROSS JOIN const_program_type p;

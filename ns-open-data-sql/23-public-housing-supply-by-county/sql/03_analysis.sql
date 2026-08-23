-- 03_analysis.sql
-- All of the analysis. Shares are computed on DECIMAL, not floating point,
-- and rounded to two decimals only at the end. Every section gets its rank
-- from a row_number over an ordering that is already unique, so the export
-- order in 99_export.sql never depends on scan order.

-- Provincial totals over the kept rows. Every later breakdown re-sums to
-- these two numbers; the reconciliation section proves it inside the output.
CREATE OR REPLACE TABLE provincial AS
SELECT
    CAST(sum(units) AS BIGINT) AS units,
    CAST(count(*)   AS BIGINT) AS properties
FROM housing_long;

-- The 36 grid cells: county by program type, zeros materialized by the cross
-- join in 02_transform.sql rather than left missing.
CREATE OR REPLACE TABLE cell_totals AS
SELECT
    g.county,
    g.program_type,
    g.program_order,
    CAST(COALESCE(sum(h.units), 0) AS BIGINT) AS units,
    CAST(count(h.source_id) AS BIGINT)        AS properties
FROM county_grid g
LEFT JOIN housing_long h
       ON h.county = g.county
      AND h.program_type = g.program_type
GROUP BY g.county, g.program_type, g.program_order;

-- County totals across both program types, ranked by units with the county
-- name breaking any tie so the rank is reproducible.
CREATE OR REPLACE TABLE county_ranked AS
SELECT
    county,
    CAST(sum(units) AS BIGINT)      AS units,
    CAST(sum(properties) AS BIGINT) AS properties,
    CAST(row_number() OVER (ORDER BY sum(units) DESC, county) AS INTEGER) AS county_rank
FROM cell_totals
GROUP BY county;

-- Program totals, driven off the constant so a program type with no kept
-- rows would still show as a zero line.
CREATE OR REPLACE TABLE program_ranked AS
SELECT
    p.program_type,
    p.program_order,
    CAST(COALESCE(sum(h.units), 0) AS BIGINT) AS units,
    CAST(count(h.source_id) AS BIGINT)        AS properties,
    CAST(row_number() OVER (ORDER BY COALESCE(sum(h.units), 0) DESC, p.program_type) AS INTEGER) AS program_rank
FROM const_program_type p
LEFT JOIN housing_long h ON h.program_type = p.program_type
GROUP BY p.program_type, p.program_order;

-- Per-source unit and property totals straight off the stacked table, used by
-- the reconciliation section. These are deliberately computed from
-- housing_long rather than from cell_totals, so the reconciliation compares
-- two independent paths to the same number.
CREATE OR REPLACE TABLE source_totals AS
SELECT
    program_type,
    CAST(sum(units) AS BIGINT) AS units,
    CAST(count(*)   AS BIGINT) AS properties
FROM housing_long
GROUP BY program_type;

-- Scalars the summary, exclusions, and reconciliation sections read.
CREATE OR REPLACE TABLE run_scalars AS
SELECT
    (SELECT units FROM provincial)                                     AS prov_units,
    (SELECT properties FROM provincial)                                AS prov_properties,
    (SELECT CAST(count(*) AS BIGINT) FROM county_universe)             AS counties,
    (SELECT CAST(count(*) AS BIGINT) FROM const_program_type)          AS program_types,
    (SELECT CAST(count(*) AS BIGINT) FROM county_grid)                 AS grid_cells,
    (SELECT CAST(count(*) AS BIGINT) FROM cell_totals WHERE units = 0) AS zero_cells,
    (SELECT CAST(count(*) AS BIGINT) FROM cell_totals
      WHERE program_type = 'Families' AND units = 0)                   AS counties_no_families,
    (SELECT CAST(count(*) AS BIGINT) FROM cell_totals
      WHERE program_type = 'Seniors'  AND units = 0)                   AS counties_no_seniors,
    (SELECT CAST(COALESCE(sum(county_substituted), 0) AS BIGINT)
       FROM stacked_norm)                                              AS county_subs,
    (SELECT CAST(COALESCE(sum(authority_substituted), 0) AS BIGINT)
       FROM stacked_norm)                                              AS authority_subs,
    (SELECT county FROM county_ranked WHERE county_rank = 1)           AS top_county,
    (SELECT units  FROM county_ranked WHERE county_rank = 1)           AS top_county_units,
    (SELECT CAST(count(*) AS BIGINT) FROM raw_families)                AS read_families,
    (SELECT CAST(count(*) AS BIGINT) FROM raw_seniors)                 AS read_seniors,
    (SELECT CAST(count(*) AS BIGINT) FROM excluded_rows
      WHERE exclusion_reason = 'county_blank')                         AS exc_county_blank,
    (SELECT CAST(count(*) AS BIGINT) FROM excluded_rows
      WHERE exclusion_reason = 'units_not_a_number')                   AS exc_units_nan,
    (SELECT CAST(count(*) AS BIGINT) FROM excluded_rows
      WHERE exclusion_reason = 'units_not_positive')                   AS exc_units_low,
    (SELECT CAST(count(*) AS BIGINT) FROM excluded_rows)               AS exc_total,
    (SELECT CAST(count(*) AS BIGINT) FROM housing_long)                AS kept_total,
    (SELECT CAST(COALESCE(sum(units), 0) AS BIGINT) FROM housing_long
      WHERE program_type = 'Families')                                 AS units_families,
    (SELECT CAST(COALESCE(sum(units), 0) AS BIGINT) FROM housing_long
      WHERE program_type = 'Seniors')                                  AS units_seniors,
    (SELECT CAST(COALESCE(sum(properties), 0) AS BIGINT) FROM source_totals
      WHERE program_type = 'Families')                                 AS props_families,
    (SELECT CAST(COALESCE(sum(properties), 0) AS BIGINT) FROM source_totals
      WHERE program_type = 'Seniors')                                  AS props_seniors,
    (SELECT CAST(COALESCE(sum(units), 0) AS BIGINT) FROM cell_totals)  AS grid_units,
    (SELECT CAST(COALESCE(sum(properties), 0) AS BIGINT) FROM cell_totals) AS grid_properties;

-- The sectioned result. Sections stack in a fixed order; within a section the
-- rank is already unique, and the export still appends county then
-- program_type as the final tie-breakers.
CREATE OR REPLACE TABLE housing_supply AS
WITH s AS (SELECT * FROM run_scalars),

summary AS (
    SELECT 1 AS ord, m.rank, m.measure, m.county, m.value, m.share_pct
    FROM s, LATERAL (
        VALUES
            (1,  'provincial_units',              NULL,          s.prov_units,        CAST(100.00 AS DECIMAL(9,2))),
            (2,  'provincial_properties',         NULL,          s.prov_properties,   NULL),
            (3,  'counties_in_universe',          NULL,          s.counties,          NULL),
            (4,  'program_types',                 NULL,          s.program_types,     NULL),
            (5,  'grid_cells',                    NULL,          s.grid_cells,        NULL),
            (6,  'grid_cells_with_zero_units',    NULL,          s.zero_cells,        NULL),
            (7,  'counties_without_family_units', NULL,          s.counties_no_families, NULL),
            (8,  'counties_without_senior_units', NULL,          s.counties_no_seniors,  NULL),
            (9,  'county_name_substitutions',     NULL,          s.county_subs,       NULL),
            (10, 'authority_name_substitutions',  NULL,          s.authority_subs,    NULL),
            (11, 'top_county_units',              s.top_county,  s.top_county_units,
                 CAST(round(CAST(s.top_county_units AS DECIMAL(18,6)) * 100
                            / CAST(s.prov_units AS DECIMAL(18,6)), 2) AS DECIMAL(9,2)))
    ) AS m(rank, measure, county, value, share_pct)
),

exclusions AS (
    SELECT 2 AS ord, m.rank, m.measure, m.value
    FROM s, LATERAL (
        VALUES
            (1, 'rows_read_families',           s.read_families),
            (2, 'rows_read_seniors',            s.read_seniors),
            (3, 'rows_read_total',              s.read_families + s.read_seniors),
            (4, 'excluded_county_blank',        s.exc_county_blank),
            (5, 'excluded_units_not_a_number',  s.exc_units_nan),
            (6, 'excluded_units_not_positive',  s.exc_units_low),
            (7, 'excluded_total',               s.exc_total),
            (8, 'rows_kept_total',              s.kept_total),
            (9, 'row_accounting_difference',
                s.read_families + s.read_seniors - s.exc_total - s.kept_total)
    ) AS m(rank, measure, value)
),

reconciliation AS (
    SELECT 3 AS ord, m.rank, m.measure, m.value
    FROM s, LATERAL (
        VALUES
            (1,  'units_families',                       s.units_families),
            (2,  'units_seniors',                        s.units_seniors),
            (3,  'units_sum_of_sources',                 s.units_families + s.units_seniors),
            (4,  'units_combined_total',                 s.prov_units),
            (5,  'units_sources_minus_combined',         s.units_families + s.units_seniors - s.prov_units),
            (6,  'units_sum_of_county_grid',             s.grid_units),
            (7,  'units_grid_minus_combined',            s.grid_units - s.prov_units),
            (8,  'properties_families',                  s.props_families),
            (9,  'properties_seniors',                   s.props_seniors),
            (10, 'properties_sum_of_sources',            s.props_families + s.props_seniors),
            (11, 'properties_combined_total',            s.prov_properties),
            (12, 'properties_sources_minus_combined',    s.props_families + s.props_seniors - s.prov_properties),
            (13, 'properties_sum_of_county_grid',        s.grid_properties),
            (14, 'properties_grid_minus_combined',       s.grid_properties - s.prov_properties)
    ) AS m(rank, measure, value)
),

program_section AS (
    SELECT
        4 AS ord,
        program_rank AS rank,
        program_type,
        properties,
        units,
        CAST(round(CAST(units AS DECIMAL(18,6)) * 100
                   / CAST((SELECT prov_units FROM s) AS DECIMAL(18,6)), 2) AS DECIMAL(9,2)) AS share_pct
    FROM program_ranked
),

county_section AS (
    SELECT
        5 AS ord,
        county_rank AS rank,
        county,
        properties,
        units,
        CAST(round(CAST(units AS DECIMAL(18,6)) * 100
                   / CAST((SELECT prov_units FROM s) AS DECIMAL(18,6)), 2) AS DECIMAL(9,2)) AS share_pct
    FROM county_ranked
),

grid_section AS (
    SELECT
        6 AS ord,
        CAST(row_number() OVER (ORDER BY r.county_rank, c.program_order) AS INTEGER) AS rank,
        c.county,
        c.program_type,
        c.properties,
        c.units,
        CAST(round(CAST(c.units AS DECIMAL(18,6)) * 100
                   / CAST((SELECT prov_units FROM s) AS DECIMAL(18,6)), 2) AS DECIMAL(9,2)) AS share_pct
    FROM cell_totals c
    JOIN county_ranked r ON r.county = c.county
)

SELECT 'summary' AS section, ord AS section_order, CAST(rank AS INTEGER) AS rank,
       measure, county, CAST(NULL AS VARCHAR) AS program_type,
       CAST(NULL AS BIGINT) AS properties, CAST(NULL AS BIGINT) AS units,
       share_pct, CAST(value AS BIGINT) AS value
FROM summary
UNION ALL
SELECT 'exclusions', ord, CAST(rank AS INTEGER), measure, NULL, NULL,
       NULL, NULL, CAST(NULL AS DECIMAL(9,2)), CAST(value AS BIGINT)
FROM exclusions
UNION ALL
SELECT 'reconciliation', ord, CAST(rank AS INTEGER), measure, NULL, NULL,
       NULL, NULL, CAST(NULL AS DECIMAL(9,2)), CAST(value AS BIGINT)
FROM reconciliation
UNION ALL
SELECT 'program_totals', ord, rank, NULL, NULL, program_type,
       properties, units, share_pct, CAST(NULL AS BIGINT)
FROM program_section
UNION ALL
SELECT 'county_totals', ord, rank, NULL, county, NULL,
       properties, units, share_pct, CAST(NULL AS BIGINT)
FROM county_section
UNION ALL
SELECT 'county_program', ord, rank, NULL, county, program_type,
       properties, units, share_pct, CAST(NULL AS BIGINT)
FROM grid_section;

-- The BI mart: one row per kept property record, the grain Tableau reads.
-- Its units column sums to the same provincial total the result proves.
CREATE OR REPLACE TABLE mart_housing AS
SELECT
    program_type,
    source_id,
    county,
    municipality,
    community,
    property_label,
    housing_authority,
    units,
    latitude,
    longitude
FROM housing_long;

-- 02_transform.sql
-- Typing, row classification, and port identity. Every rule here is
-- deterministic and every excluded row lands in a class that 03_analysis.sql
-- counts and reports. Nothing is dropped quietly and nothing blank ever
-- becomes zero.

-- Step 1: type the snapshot and put every source row into exactly one grain
-- class and exactly one measure class.
--
-- Grain class (row_grain):
--   'county_total'  the published 'Total for <County> County' aggregate row,
--                   identified by constants.county_total_prefix. A different
--                   grain from a port row, so it is excluded from every port,
--                   county, and year sum. It is kept in this table and used in
--                   the coverage section, where the province's own county
--                   figure is compared against the sum of that county's ports.
--   'port'          a real port record. The source is buyer purchase data, so
--                   one port in one year can carry several rows (several
--                   buyers), some of them suppressed. Those rows sum; they are
--                   not duplicates and are not deduplicated.
--
-- Measure class, applied per measure, never coerced to zero:
--   'both_present'  kilograms and dollars both reported
--   'kgs_only'      kilograms reported, dollars suppressed
--   'dollars_only'  dollars reported, kilograms suppressed
--   'both_blank'    both suppressed
CREATE OR REPLACE TABLE classified AS
SELECT
    CAST(trim(year) AS INTEGER)                        AS year,
    regexp_replace(trim(port), ' +', ' ', 'g')         AS port,
    regexp_replace(trim(county), ' +', ' ', 'g')       AS county,
    CAST(NULLIF(trim(kgs), '') AS DECIMAL(18,2))       AS kgs,
    CAST(NULLIF(trim(purchase_total), '') AS DECIMAL(18,2)) AS dollars,
    CASE
        WHEN starts_with(trim(port), (SELECT county_total_prefix FROM constants))
        THEN 'county_total'
        ELSE 'port'
    END AS row_grain,
    CASE
        WHEN NULLIF(trim(kgs), '') IS NOT NULL
         AND NULLIF(trim(purchase_total), '') IS NOT NULL THEN 'both_present'
        WHEN NULLIF(trim(kgs), '') IS NOT NULL
         AND NULLIF(trim(purchase_total), '') IS NULL     THEN 'kgs_only'
        WHEN NULLIF(trim(kgs), '') IS NULL
         AND NULLIF(trim(purchase_total), '') IS NOT NULL THEN 'dollars_only'
        ELSE 'both_blank'
    END AS measure_class
FROM raw_landings;

-- Step 2: roll a wharf qualifier back into its port.
--
-- In 2019 and 2020, and in those two years only, the province writes the wharf
-- out: 'Lower Woods Harbour (Falls Point)', 'Lunenburg (Railway Wharf)',
-- 'Freeport (South Cove)', 'Shag Harbour (Prospect Point)'. In the other six
-- years the same wharves appear as repeated bare rows under the port name. Left
-- alone, one port would rank as several, and its landed value would be split
-- across labels for two years out of eight.
--
-- The rule: a port written 'Base (Qualifier)' is the port 'Base' when 'Base'
-- also appears as a port name in the same county. That condition is what keeps
-- the rule structural rather than interpretive. A parenthesised name with no
-- bare counterpart in its county would be left exactly as published, because
-- then the qualifier is the only name that port has.
CREATE OR REPLACE TABLE port_qualifier_map AS
WITH published AS (
    SELECT DISTINCT county, port FROM classified WHERE row_grain = 'port'
),
split AS (
    SELECT
        county,
        port AS port_published,
        CASE
            WHEN strpos(port, '(') > 1
            THEN trim(substr(port, 1, strpos(port, '(') - 1))
            ELSE ''
        END AS port_base
    FROM published
)
SELECT
    s.county,
    s.port_published,
    CASE
        WHEN s.port_base <> '' AND b.port IS NOT NULL THEN s.port_base
        ELSE s.port_published
    END AS port,
    CASE
        WHEN s.port_base <> '' AND b.port IS NOT NULL THEN 1
        ELSE 0
    END AS wharf_qualifier_merged
FROM split s
LEFT JOIN published b
       ON b.county = s.county
      AND b.port   = s.port_base;

-- Step 3: port names are not unique across the province. 'Other' appears in
-- all 18 counties, 'Little Harbour' in 6, 'Little River' in 2. Grouping on the
-- bare name would silently merge separate places, so port identity is the
-- (county, port) pair and the display label only carries the county when the
-- name needs disambiguating.
CREATE OR REPLACE TABLE port_name_spread AS
SELECT m.port, count(DISTINCT m.county) AS county_count
FROM classified c
JOIN port_qualifier_map m
  ON m.county = c.county AND m.port_published = c.port
WHERE c.row_grain = 'port'
GROUP BY m.port;

-- Step 4: the analysis base. Port rows only, carrying the rolled-up port
-- identity, a stable display label, and a flag separating real ports from the
-- residual 'Other' bucket.
CREATE OR REPLACE TABLE clean_landings AS
SELECT
    c.year,
    c.county,
    m.port,
    CASE
        WHEN s.county_count > 1 THEN m.port || ' (' || c.county || ')'
        ELSE m.port
    END AS port_label,
    CASE
        WHEN m.port = (SELECT residual_port_label FROM constants) THEN 0
        ELSE 1
    END AS is_named_port,
    m.wharf_qualifier_merged,
    c.kgs,
    c.dollars,
    c.measure_class
FROM classified c
JOIN port_qualifier_map m
  ON m.county = c.county AND m.port_published = c.port
JOIN port_name_spread s
  ON s.port = m.port
WHERE c.row_grain = 'port';

-- Step 5: the province's own county figures, held aside for the coverage
-- section. These are the excluded aggregate rows, kept visible rather than
-- thrown away.
CREATE OR REPLACE TABLE published_county_totals AS
SELECT
    year,
    county,
    kgs     AS published_kgs,
    dollars AS published_dollars
FROM classified
WHERE row_grain = 'county_total';

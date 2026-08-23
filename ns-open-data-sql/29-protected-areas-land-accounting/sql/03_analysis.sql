-- 03_analysis.sql
-- Land accounting over the cleaned records: hectares by designation, by
-- authority, by owner, and by status, each with record counts and a share of
-- the provincial protected total, plus the concentration curve.
--
-- Every result query ends in a total ORDER BY whose last term is unique, so row
-- order is fixed regardless of engine, version, or scan order.

-- ---------------------------------------------------------------------------
-- Grand totals. Every breakdown below has to re-sum to grand.total_hectares.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE grand AS
SELECT
    CAST(sum(hectares) AS DECIMAL(18, 2))            AS total_hectares,
    CAST(count(*) AS BIGINT)                         AS total_records,
    CAST(round(sum(hectares_unrounded), 2) AS DECIMAL(18, 2)) AS unrounded_total_hectares
FROM protected_records;

-- ---------------------------------------------------------------------------
-- Breakdowns. Each is grouped on one label, so the label itself is the unique
-- tie-breaker at the end of the sort.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE by_designation AS
SELECT
    designation,
    CAST(count(*) AS BIGINT)                  AS records,
    CAST(sum(hectares) AS DECIMAL(18, 2))     AS hectares
FROM protected_records
GROUP BY designation;

CREATE OR REPLACE TABLE by_authority AS
SELECT
    authority,
    CAST(count(*) AS BIGINT)                  AS records,
    CAST(sum(hectares) AS DECIMAL(18, 2))     AS hectares
FROM protected_records
GROUP BY authority;

CREATE OR REPLACE TABLE by_owner AS
SELECT
    owner,
    CAST(count(*) AS BIGINT)                  AS records,
    CAST(sum(hectares) AS DECIMAL(18, 2))     AS hectares
FROM protected_records
GROUP BY owner;

CREATE OR REPLACE TABLE by_status AS
SELECT
    status,
    CAST(count(*) AS BIGINT)                  AS records,
    CAST(sum(hectares) AS DECIMAL(18, 2))     AS hectares
FROM protected_records
GROUP BY status;

-- ---------------------------------------------------------------------------
-- Concentration milestones: how few records it takes to cover half, then
-- ninety per cent, of all protected hectares.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE concentration_milestones AS
SELECT
    (SELECT min(c.record_rank) FROM cumulative_records AS c, grand AS g, constants AS k
      WHERE c.cumulative_hectares >= k.half_share * g.total_hectares)   AS records_for_half,
    (SELECT min(c.record_rank) FROM cumulative_records AS c, grand AS g, constants AS k
      WHERE c.cumulative_hectares >= k.ninety_share * g.total_hectares) AS records_for_ninety,
    (SELECT CAST(sum(c.hectares) AS DECIMAL(18, 2)) FROM cumulative_records AS c
      WHERE c.record_rank <= 10)                                       AS top_10_hectares;

-- ---------------------------------------------------------------------------
-- The sectioned result.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE protected_areas AS

-- 1. summary -----------------------------------------------------------------
SELECT
    'summary'                                        AS section,
    1                                                AS section_order,
    CAST(s.rank AS BIGINT)                           AS rank,
    s.measure                                        AS measure,
    s.designation                                    AS designation,
    CAST(NULL AS VARCHAR)                            AS authority,
    CAST(NULL AS VARCHAR)                            AS owner,
    s.status                                         AS status,
    s.area_name                                      AS area_name,
    s.records                                        AS records,
    s.hectares                                       AS hectares,
    s.share_pct                                      AS share_pct,
    CAST(NULL AS DECIMAL(18, 2))                     AS cumulative_hectares,
    CAST(NULL AS DECIMAL(9, 2))                      AS cumulative_share_pct
FROM (
    SELECT 1 AS rank, 'total_protected_hectares' AS measure,
           CAST(NULL AS VARCHAR) AS designation, CAST(NULL AS VARCHAR) AS status,
           CAST(NULL AS VARCHAR) AS area_name, CAST(NULL AS BIGINT) AS records,
           g.total_hectares AS hectares, CAST(100.00 AS DECIMAL(9, 2)) AS share_pct
    FROM grand AS g
    UNION ALL
    SELECT 2, 'protected_area_records', NULL, NULL, NULL,
           g.total_records, NULL, NULL
    FROM grand AS g
    UNION ALL
    SELECT 3, 'distinct_area_names', NULL, NULL, NULL,
           (SELECT count(DISTINCT area_name) FROM protected_records), NULL, NULL
    UNION ALL
    SELECT 4, 'designation_types', NULL, NULL, NULL,
           (SELECT count(*) FROM by_designation), NULL, NULL
    UNION ALL
    SELECT 5, 'authorities', NULL, NULL, NULL,
           (SELECT count(*) FROM by_authority), NULL, NULL
    UNION ALL
    SELECT 6, 'land_owners', NULL, NULL, NULL,
           (SELECT count(*) FROM by_owner), NULL, NULL
    UNION ALL
    SELECT 7, 'provincial_land_area_hectares', NULL, NULL, NULL,
           NULL, k.ns_land_area_ha, NULL
    FROM constants AS k
    UNION ALL
    SELECT 8, 'share_of_provincial_land_pct', NULL, NULL, NULL,
           NULL, NULL,
           CAST(round(100.0 * g.total_hectares / k.ns_land_area_ha, 2) AS DECIMAL(9, 2))
    FROM grand AS g, constants AS k
    UNION ALL
    SELECT 9, 'largest_record_hectares', c.designation, NULL, c.area_name,
           NULL, c.hectares,
           CAST(round(100.0 * c.hectares / g.total_hectares, 2) AS DECIMAL(9, 2))
    FROM cumulative_records AS c, grand AS g
    WHERE c.record_rank = 1
    UNION ALL
    SELECT 10, 'top_10_records_hectares', NULL, NULL, NULL,
           10, m.top_10_hectares,
           CAST(round(100.0 * m.top_10_hectares / g.total_hectares, 2) AS DECIMAL(9, 2))
    FROM concentration_milestones AS m, grand AS g
    UNION ALL
    SELECT 11, 'records_for_half_of_hectares', NULL, NULL, NULL,
           m.records_for_half, NULL, NULL
    FROM concentration_milestones AS m
    UNION ALL
    SELECT 12, 'records_for_ninety_pct_of_hectares', NULL, NULL, NULL,
           m.records_for_ninety, NULL, NULL
    FROM concentration_milestones AS m
    UNION ALL
    SELECT 13, 'legally_designated_hectares', NULL, b.status, NULL,
           b.records, b.hectares,
           CAST(round(100.0 * b.hectares / g.total_hectares, 2) AS DECIMAL(9, 2))
    FROM by_status AS b, grand AS g, constants AS k
    WHERE b.status = k.designated_status
) AS s

UNION ALL

-- 2. coverage ----------------------------------------------------------------
-- Nothing is dropped anywhere in this pipeline. Every class that could look
-- like a silent drop is counted here instead, in hectares as well as records.
SELECT
    'coverage', 2, CAST(c.rank AS BIGINT), c.measure,
    NULL, NULL, NULL, NULL, NULL,
    c.records, c.hectares, NULL, NULL, NULL
FROM (
    SELECT 1 AS rank, 'snapshot_records' AS measure,
           (SELECT count(*) FROM raw_protected) AS records,
           CAST(NULL AS DECIMAL(18, 2)) AS hectares
    UNION ALL
    SELECT 2, 'records_loaded',
           (SELECT count(*) FROM protected_records), NULL
    UNION ALL
    SELECT 3, 'records_dropped_in_cleaning',
           (SELECT count(*) FROM raw_protected)
             - (SELECT count(*) FROM protected_records), NULL
    UNION ALL
    SELECT 4, 'records_zero_or_negative_hectares',
           (SELECT count(*) FROM protected_records WHERE hectares <= 0), NULL
    UNION ALL
    SELECT 5, 'distinct_area_names',
           (SELECT count(DISTINCT area_name) FROM protected_records), NULL
    UNION ALL
    SELECT 6, 'records_sharing_an_area_name',
           (SELECT count(*) FROM protected_records AS p
             WHERE (SELECT count(*) FROM protected_records AS q
                     WHERE q.area_name = p.area_name) > 1), NULL
    UNION ALL
    SELECT 7, 'authority_labels_rewritten',
           (SELECT sum(authority_renamed) FROM protected_records), NULL
    UNION ALL
    SELECT 8, 'owner_labels_rewritten',
           (SELECT sum(owner_renamed) FROM protected_records), NULL
    UNION ALL
    SELECT 9, 'records_missing_designation_year',
           (SELECT count(*) FROM protected_records WHERE designation_year IS NULL),
           (SELECT CAST(coalesce(sum(hectares), 0) AS DECIMAL(18, 2))
              FROM protected_records WHERE designation_year IS NULL)
    UNION ALL
    SELECT 10, 'records_in_year_series',
           (SELECT count(*) FROM protected_records WHERE designation_year IS NOT NULL),
           (SELECT CAST(coalesce(sum(hectares), 0) AS DECIMAL(18, 2))
              FROM protected_records WHERE designation_year IS NOT NULL)
    UNION ALL
    SELECT 11, 'unrounded_total_hectares',
           NULL, (SELECT unrounded_total_hectares FROM grand)
    UNION ALL
    SELECT 12, 'record_rounding_difference_hectares',
           NULL, (SELECT total_hectares - unrounded_total_hectares FROM grand)
) AS c

UNION ALL

-- 3. totals_tie --------------------------------------------------------------
-- Four independent re-summations of the same land. All four must read the
-- grand total exactly, because hectares were rounded once at the record level.
SELECT
    'totals_tie', 3, CAST(t.rank AS BIGINT), t.measure,
    NULL, NULL, NULL, NULL, NULL,
    t.records, t.hectares,
    CAST(round(100.0 * t.hectares / (SELECT total_hectares FROM grand), 2) AS DECIMAL(9, 2)),
    NULL, NULL
FROM (
    SELECT 1 AS rank, 'sum_by_designation' AS measure,
           CAST(sum(records) AS BIGINT) AS records,
           CAST(sum(hectares) AS DECIMAL(18, 2)) AS hectares
    FROM by_designation
    UNION ALL
    SELECT 2, 'sum_by_authority', CAST(sum(records) AS BIGINT),
           CAST(sum(hectares) AS DECIMAL(18, 2)) FROM by_authority
    UNION ALL
    SELECT 3, 'sum_by_owner', CAST(sum(records) AS BIGINT),
           CAST(sum(hectares) AS DECIMAL(18, 2)) FROM by_owner
    UNION ALL
    SELECT 4, 'sum_by_status', CAST(sum(records) AS BIGINT),
           CAST(sum(hectares) AS DECIMAL(18, 2)) FROM by_status
    UNION ALL
    SELECT 5, 'last_row_of_concentration_curve', CAST(max(record_rank) AS BIGINT),
           CAST(max(cumulative_hectares) AS DECIMAL(18, 2)) FROM cumulative_records
) AS t

UNION ALL

-- 4. by_designation ----------------------------------------------------------
-- protect1 is used verbatim. Compound labels such as "Wilderness Area,
-- Conservation Easement" stay whole, so no hectare is counted twice.
SELECT
    'by_designation', 4,
    CAST(row_number() OVER (ORDER BY d.hectares DESC, d.designation) AS BIGINT),
    NULL, d.designation, NULL, NULL, NULL, NULL,
    d.records, d.hectares,
    CAST(round(100.0 * d.hectares / (SELECT total_hectares FROM grand), 2) AS DECIMAL(9, 2)),
    NULL, NULL
FROM by_designation AS d

UNION ALL

-- 5. by_authority ------------------------------------------------------------
SELECT
    'by_authority', 5,
    CAST(row_number() OVER (ORDER BY a.hectares DESC, a.authority) AS BIGINT),
    NULL, NULL, a.authority, NULL, NULL, NULL,
    a.records, a.hectares,
    CAST(round(100.0 * a.hectares / (SELECT total_hectares FROM grand), 2) AS DECIMAL(9, 2)),
    NULL, NULL
FROM by_authority AS a

UNION ALL

-- 6. by_owner ----------------------------------------------------------------
SELECT
    'by_owner', 6,
    CAST(row_number() OVER (ORDER BY o.hectares DESC, o.owner) AS BIGINT),
    NULL, NULL, NULL, o.owner, NULL, NULL,
    o.records, o.hectares,
    CAST(round(100.0 * o.hectares / (SELECT total_hectares FROM grand), 2) AS DECIMAL(9, 2)),
    NULL, NULL
FROM by_owner AS o

UNION ALL

-- 7. by_status ---------------------------------------------------------------
SELECT
    'by_status', 7,
    CAST(row_number() OVER (ORDER BY b.hectares DESC, b.status) AS BIGINT),
    NULL, NULL, NULL, NULL, b.status, NULL,
    b.records, b.hectares,
    CAST(round(100.0 * b.hectares / (SELECT total_hectares FROM grand), 2) AS DECIMAL(9, 2)),
    NULL, NULL
FROM by_status AS b

UNION ALL

-- 8. concentration -----------------------------------------------------------
-- The largest records first, with the running hectare total beside them. This
-- is the ordered axis the BI running total reproduces.
SELECT
    'concentration', 8, CAST(c.record_rank AS BIGINT),
    NULL, c.designation, c.authority, NULL, c.status, c.area_name,
    CAST(1 AS BIGINT), c.hectares,
    CAST(round(100.0 * c.hectares / (SELECT total_hectares FROM grand), 2) AS DECIMAL(9, 2)),
    c.cumulative_hectares,
    CAST(round(100.0 * c.cumulative_hectares / (SELECT total_hectares FROM grand), 2) AS DECIMAL(9, 2))
FROM cumulative_records AS c
WHERE c.record_rank <= (SELECT concentration_top_n FROM constants);

-- ---------------------------------------------------------------------------
-- The BI mart: one row per published record, carrying the integer ordered axis
-- and the integer designation_year, and no date column of any kind.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE mart_protected AS
SELECT
    objectid,
    area_name,
    designation,
    authority,
    owner,
    status,
    hectares,
    designation_year,
    record_rank
FROM cumulative_records;

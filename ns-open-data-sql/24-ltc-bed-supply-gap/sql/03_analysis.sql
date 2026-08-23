-- 03_analysis: every figure this build reports.
--
-- The bed definition the whole file rests on:
--     total_beds = nursing_homes_nh_no_of_beds
--                + residential_care_facilities_rcf_no_of_beds
-- Respite beds (nursing_homes_nh_no_of_respite_beds and rcf_respite_beds) are
-- carried as their own bed types and stay out of total_beds.
--
-- Median: DuckDB's MEDIAN is the continuous median, the same thing as
-- QUANTILE_CONT(x, 0.5). With an even facility count it interpolates between the
-- two middle values, so a zone can report a half bed. Averages and medians are
-- rounded to params.round_dp decimals and stored as DECIMAL(12,2) so the CSV is
-- byte-stable.
--
-- No population source is carried, so nothing here is per capita.

-- Facility grain, with the core total and the respite side kept apart.
CREATE OR REPLACE TABLE facility_totals AS
SELECT
    f.facility_id,
    f.facility_name,
    f.town,
    f.postal_code,
    f.zone,
    f.facility_type,
    f.sea_participating,
    f.longitude,
    f.latitude,
    f.nursing_beds,
    f.residential_beds,
    f.nursing_beds + f.residential_beds AS total_beds,
    f.nursing_respite_beds,
    f.residential_respite_beds,
    f.nursing_respite_beds + f.residential_respite_beds AS respite_beds
FROM ltc_facility f;

-- Provincial totals. Every breakdown below has to re-sum to grand.total_beds.
CREATE OR REPLACE TABLE grand AS
SELECT
    COUNT(*)                                        AS facilities,
    SUM(total_beds)                                 AS total_beds,
    SUM(nursing_beds)                               AS nursing_beds,
    SUM(residential_beds)                           AS residential_beds,
    SUM(nursing_respite_beds)                       AS nursing_respite_beds,
    SUM(residential_respite_beds)                   AS residential_respite_beds,
    SUM(respite_beds)                               AS respite_beds,
    CAST(ROUND(AVG(total_beds), (SELECT round_dp FROM params)) AS DECIMAL(12,2))    AS avg_beds,
    CAST(ROUND(MEDIAN(total_beds), (SELECT round_dp FROM params)) AS DECIMAL(12,2)) AS median_beds,
    SUM(CASE WHEN sea_participating = (SELECT sea_yes_flag FROM params)
             THEN 1 ELSE 0 END)                     AS sea_facilities
FROM facility_totals;

-- Row accounting. Every class in ltc_classified gets a count, whether or not the
-- snapshot happens to contain one.
CREATE OR REPLACE TABLE row_accounting AS
WITH classes(class_ord, row_class) AS (
    VALUES
        (1, 'excluded_missing_facility_id'),
        (2, 'excluded_duplicate_facility_id'),
        (3, 'excluded_non_numeric_beds'),
        (4, 'excluded_negative_beds'),
        (5, 'excluded_fractional_beds'),
        (6, 'excluded_unknown_zone')
)
SELECT 1 AS ord, 'rows_read' AS measure,
       (SELECT COUNT(*) FROM ltc_raw) AS n
UNION ALL
SELECT 2, 'rows_kept', (SELECT COUNT(*) FROM ltc_facility)
UNION ALL
SELECT 2 + c.class_ord, c.row_class,
       (SELECT COUNT(*) FROM ltc_classified x WHERE x.row_class = c.row_class)
FROM classes c
UNION ALL
SELECT 9, 'rows_read_minus_kept_and_excluded',
       (SELECT COUNT(*) FROM ltc_raw)
       - (SELECT COUNT(*) FROM ltc_classified)
UNION ALL
SELECT 10, 'snapshot_row_count_matches_params',
       CASE WHEN (SELECT COUNT(*) FROM ltc_raw)
                 = (SELECT snapshot_row_count FROM params)
            THEN 1 ELSE 0 END;

-- Zone rollup. Ranked by beds; the zone name is the unique tie-breaker.
CREATE OR REPLACE TABLE zone_totals AS
SELECT
    z.zone_ord,
    f.zone,
    COUNT(*)                                                            AS facilities,
    SUM(f.total_beds)                                                   AS total_beds,
    SUM(f.nursing_beds)                                                 AS nursing_beds,
    SUM(f.residential_beds)                                             AS residential_beds,
    SUM(f.nursing_respite_beds)                                         AS nursing_respite_beds,
    SUM(f.residential_respite_beds)                                     AS residential_respite_beds,
    CAST(ROUND(AVG(f.total_beds), p.round_dp)    AS DECIMAL(12,2))      AS avg_beds,
    CAST(ROUND(MEDIAN(f.total_beds), p.round_dp) AS DECIMAL(12,2))      AS median_beds,
    CAST(ROUND(100.0 * SUM(f.total_beds) / g.total_beds, p.round_dp)
         AS DECIMAL(7,2))                                               AS share_pct
FROM facility_totals f
JOIN zone_dim z USING (zone)
CROSS JOIN params p
CROSS JOIN grand g
GROUP BY z.zone_ord, f.zone, p.round_dp, g.total_beds;

-- Facility-type rollup, the published type label as written.
CREATE OR REPLACE TABLE type_totals AS
SELECT
    f.facility_type,
    COUNT(*)                                                       AS facilities,
    SUM(f.total_beds)                                              AS total_beds,
    SUM(f.nursing_beds)                                            AS nursing_beds,
    SUM(f.residential_beds)                                        AS residential_beds,
    CAST(ROUND(AVG(f.total_beds), p.round_dp) AS DECIMAL(12,2))    AS avg_beds,
    CAST(ROUND(MEDIAN(f.total_beds), p.round_dp) AS DECIMAL(12,2)) AS median_beds,
    CAST(ROUND(100.0 * SUM(f.total_beds) / g.total_beds, p.round_dp)
         AS DECIMAL(7,2))                                          AS share_pct
FROM facility_totals f
CROSS JOIN params p
CROSS JOIN grand g
GROUP BY f.facility_type, p.round_dp, g.total_beds;

-- Bed-type rollup. share_pct is the share of total_beds, so it is filled for the
-- two core types and left blank for the two respite types, which sit outside that
-- base by definition.
CREATE OR REPLACE TABLE bed_type_totals AS
SELECT
    d.bed_type_ord,
    d.bed_type,
    d.is_core_bed,
    SUM(l.beds)                                       AS beds,
    SUM(CASE WHEN l.beds > 0 THEN 1 ELSE 0 END)       AS facilities,
    CASE WHEN d.is_core_bed = 1
         THEN CAST(ROUND(100.0 * SUM(l.beds) / g.total_beds, p.round_dp)
                   AS DECIMAL(7,2))
    END                                               AS share_pct
FROM facility_bed_long l
JOIN bed_type_dim d USING (bed_type)
CROSS JOIN params p
CROSS JOIN grand g
GROUP BY d.bed_type_ord, d.bed_type, d.is_core_bed, p.round_dp, g.total_beds;

-- The zone-by-bed-type matrix in long form: 4 zones x 4 bed types, always 16 rows
-- even where a cell is zero.
CREATE OR REPLACE TABLE zone_bed_type AS
SELECT
    z.zone_ord,
    l.zone,
    d.bed_type_ord,
    l.bed_type,
    d.is_core_bed,
    SUM(l.beds)                                 AS beds,
    SUM(CASE WHEN l.beds > 0 THEN 1 ELSE 0 END) AS facilities
FROM facility_bed_long l
JOIN zone_dim z USING (zone)
JOIN bed_type_dim d USING (bed_type)
GROUP BY z.zone_ord, l.zone, d.bed_type_ord, l.bed_type, d.is_core_bed;

-- Largest facilities by total_beds. Ties break on facility_id, which is unique.
CREATE OR REPLACE TABLE top_facilities AS
SELECT
    ROW_NUMBER() OVER (ORDER BY f.total_beds DESC, f.facility_id) AS rank,
    f.facility_id,
    f.facility_name,
    f.town,
    f.zone,
    f.facility_type,
    f.total_beds,
    f.respite_beds,
    CAST(ROUND(100.0 * f.total_beds / g.total_beds, p.round_dp)
         AS DECIMAL(7,2))                                         AS share_pct
FROM facility_totals f
CROSS JOIN params p
CROSS JOIN grand g
QUALIFY rank <= (SELECT top_facility_limit FROM params);

-- The sectioned golden result. section_ord and ord together are unique across the
-- whole table, which is what 99_export orders on.
CREATE OR REPLACE TABLE ltc_bed_supply AS

-- 1. summary
SELECT 1 AS section_ord, 'summary' AS section, s.ord,
       s.measure, NULL::VARCHAR AS zone, NULL::VARCHAR AS facility_type,
       NULL::VARCHAR AS bed_type, s.facility_id, s.facility_name, s.town,
       s.facilities, s.beds, s.share_pct, s.avg_beds, s.median_beds
FROM (
    SELECT 1 AS ord, 'facilities_total' AS measure,
           NULL::VARCHAR AS facility_id, NULL::VARCHAR AS facility_name,
           NULL::VARCHAR AS town,
           g.facilities AS facilities, NULL::BIGINT AS beds,
           NULL::DECIMAL(7,2) AS share_pct,
           NULL::DECIMAL(12,2) AS avg_beds, NULL::DECIMAL(12,2) AS median_beds
    FROM grand g
    UNION ALL
    SELECT 2, 'total_beds', NULL, NULL, NULL,
           NULL, g.total_beds, CAST(100.00 AS DECIMAL(7,2)), NULL, NULL
    FROM grand g
    UNION ALL
    SELECT 3, 'nursing_beds', NULL, NULL, NULL,
           NULL, g.nursing_beds,
           CAST(ROUND(100.0 * g.nursing_beds / g.total_beds, p.round_dp) AS DECIMAL(7,2)),
           NULL, NULL
    FROM grand g CROSS JOIN params p
    UNION ALL
    SELECT 4, 'residential_beds', NULL, NULL, NULL,
           NULL, g.residential_beds,
           CAST(ROUND(100.0 * g.residential_beds / g.total_beds, p.round_dp) AS DECIMAL(7,2)),
           NULL, NULL
    FROM grand g CROSS JOIN params p
    UNION ALL
    SELECT 5, 'nursing_respite_beds_excluded', NULL, NULL, NULL,
           NULL, g.nursing_respite_beds, NULL, NULL, NULL
    FROM grand g
    UNION ALL
    SELECT 6, 'residential_respite_beds_excluded', NULL, NULL, NULL,
           NULL, g.residential_respite_beds, NULL, NULL, NULL
    FROM grand g
    UNION ALL
    SELECT 7, 'sea_participating_facilities', NULL, NULL, NULL,
           g.sea_facilities, NULL, NULL, NULL, NULL
    FROM grand g
    UNION ALL
    SELECT 8, 'avg_beds_per_facility', NULL, NULL, NULL,
           NULL, NULL, NULL, g.avg_beds, NULL
    FROM grand g
    UNION ALL
    SELECT 9, 'median_beds_per_facility', NULL, NULL, NULL,
           NULL, NULL, NULL, NULL, g.median_beds
    FROM grand g
    UNION ALL
    SELECT 10, 'largest_facility', t.facility_id, t.facility_name, t.town,
           NULL, t.total_beds, t.share_pct, NULL, NULL
    FROM top_facilities t WHERE t.rank = 1
) s

UNION ALL

-- 2. row_accounting
SELECT 2, 'row_accounting', a.ord,
       a.measure, NULL, NULL, NULL, NULL, NULL, NULL,
       a.n, NULL, NULL, NULL, NULL
FROM row_accounting a

UNION ALL

-- 3. totals_tie: four independent re-summations of the same total_beds
SELECT 3, 'totals_tie', t.ord,
       t.measure, NULL, NULL, NULL, NULL, NULL, NULL,
       NULL, t.beds, NULL, NULL, NULL
FROM (
    SELECT 1 AS ord, 'sum_by_zone' AS measure,
           (SELECT SUM(total_beds) FROM zone_totals) AS beds
    UNION ALL
    SELECT 2, 'sum_by_facility_type',
           (SELECT SUM(total_beds) FROM type_totals)
    UNION ALL
    SELECT 3, 'sum_by_bed_type_core',
           (SELECT SUM(beds) FROM bed_type_totals WHERE is_core_bed = 1)
    UNION ALL
    SELECT 4, 'sum_by_zone_and_bed_type_core',
           (SELECT SUM(beds) FROM zone_bed_type WHERE is_core_bed = 1)
    UNION ALL
    SELECT 5, 'sum_by_facility',
           (SELECT SUM(total_beds) FROM facility_totals)
) t

UNION ALL

-- 4. zone_totals, ranked by beds with zone as the unique tie-breaker
SELECT 4, 'zone_totals',
       ROW_NUMBER() OVER (ORDER BY z.total_beds DESC, z.zone),
       NULL, z.zone, NULL, NULL, NULL, NULL, NULL,
       z.facilities, z.total_beds, z.share_pct, z.avg_beds, z.median_beds
FROM zone_totals z

UNION ALL

-- 5. type_totals, ranked by beds with facility_type as the unique tie-breaker
SELECT 5, 'type_totals',
       ROW_NUMBER() OVER (ORDER BY y.total_beds DESC, y.facility_type),
       NULL, NULL, y.facility_type, NULL, NULL, NULL, NULL,
       y.facilities, y.total_beds, y.share_pct, y.avg_beds, y.median_beds
FROM type_totals y

UNION ALL

-- 6. bed_type_totals, in the fixed bed_type_dim order
SELECT 6, 'bed_type_totals',
       ROW_NUMBER() OVER (ORDER BY b.bed_type_ord),
       NULL, NULL, NULL, b.bed_type, NULL, NULL, NULL,
       b.facilities, b.beds, b.share_pct, NULL, NULL
FROM bed_type_totals b

UNION ALL

-- 7. zone_bed_type, ordered by zone then bed_type, which is unique
SELECT 7, 'zone_bed_type',
       ROW_NUMBER() OVER (ORDER BY zb.zone, zb.bed_type),
       NULL, zb.zone, NULL, zb.bed_type, NULL, NULL, NULL,
       zb.facilities, zb.beds, NULL, NULL, NULL
FROM zone_bed_type zb

UNION ALL

-- 8. top_facilities, ranked by beds with facility_id as the unique tie-breaker
SELECT 8, 'top_facilities', t.rank,
       NULL, t.zone, t.facility_type, NULL,
       t.facility_id, t.facility_name, t.town,
       NULL, t.total_beds, t.share_pct, NULL, NULL
FROM top_facilities t;

-- The print-ready zone table behind `python run.py show`, plus a pinned province
-- row. run.py aligns the columns and prints; it computes none of this.
CREATE OR REPLACE TABLE show_beds_by_zone AS
SELECT
    ROW_NUMBER() OVER (ORDER BY z.total_beds DESC, z.zone) AS ord,
    z.zone,
    z.facilities,
    z.nursing_beds,
    z.residential_beds,
    z.total_beds,
    z.share_pct,
    z.avg_beds,
    z.median_beds,
    z.nursing_respite_beds,
    z.residential_respite_beds
FROM zone_totals z
UNION ALL
SELECT
    (SELECT COUNT(*) FROM zone_totals) + 1,
    'ALL ZONES',
    g.facilities,
    g.nursing_beds,
    g.residential_beds,
    g.total_beds,
    CAST(100.00 AS DECIMAL(7,2)),
    g.avg_beds,
    g.median_beds,
    g.nursing_respite_beds,
    g.residential_respite_beds
FROM grand g;

-- headline: finished lines. run.py prints them and formats nothing.
CREATE OR REPLACE TABLE headline AS
SELECT 1 AS ord,
       printf('%d facilities hold %d long-term care and residential care beds: %d nursing home beds and %d residential care beds.',
              g.facilities, g.total_beds, g.nursing_beds, g.residential_beds) AS line
FROM grand g
UNION ALL
SELECT 2,
       printf('%d nursing respite and %d residential care respite beds sit outside that total by definition.',
              g.nursing_respite_beds, g.residential_respite_beds)
FROM grand g
UNION ALL
SELECT 3,
       printf('Busiest zone: %s with %d beds (%.2f%% of the province) across %d facilities.',
              z.zone, z.total_beds, z.share_pct, z.facilities)
FROM zone_totals z
WHERE z.total_beds = (SELECT MAX(total_beds) FROM zone_totals)
UNION ALL
SELECT 4,
       printf('Largest single facility: %s in %s, %d beds.',
              t.facility_name, t.town, t.total_beds)
FROM top_facilities t
WHERE t.rank = 1;

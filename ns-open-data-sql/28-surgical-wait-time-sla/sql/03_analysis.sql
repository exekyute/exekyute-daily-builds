-- 03_analysis.sql
-- Every breach figure, tail-gap figure, and trend figure, then the sectioned
-- result table (wait_time_sla) and the BI mart.
--
-- Nothing here recomputes a percentile. consult_median, consult_90th,
-- surgery_median and surgery_90th are published by the source; this file
-- compares them to the named targets in 00_schema.sql, subtracts them from
-- each other to get the tail gaps, and counts.
--
-- Every table below ends in a total ORDER BY whose last terms form a unique
-- key at that grain, so row order never depends on scan order. Breach counts
-- tie heavily, which is exactly why no ranking stops at the measure.

-- Per-facility breach rates. zone rides along because each facility sits in
-- exactly one zone; it becomes the BI slicer field.
CREATE OR REPLACE TABLE facility_breach AS
SELECT
    zone,
    facility,
    count(*)                                    AS lines_total,
    sum(surgery_measured)                       AS surgery_rows,
    sum(surgery_breach)                         AS surgery_breaches,
    CAST(ROUND(100.0 * sum(surgery_breach)
               / nullif(sum(surgery_measured), 0), 2) AS DECIMAL(9,2))
                                                AS surgery_breach_pct,
    sum(consult_measured)                       AS consult_rows,
    sum(consult_breach)                         AS consult_breaches,
    CAST(ROUND(100.0 * sum(consult_breach)
               / nullif(sum(consult_measured), 0), 2) AS DECIMAL(9,2))
                                                AS consult_breach_pct,
    CASE WHEN sum(surgery_measured) >= min_measured_rows() THEN 1 ELSE 0 END
                                                AS meets_min_rows
FROM facility_lines
GROUP BY zone, facility
ORDER BY facility;

-- Per-procedure breach rates over the same facility grain.
CREATE OR REPLACE TABLE procedure_breach AS
SELECT
    procedure,
    count(*)                                    AS lines_total,
    count(DISTINCT facility)                    AS facilities,
    sum(surgery_measured)                       AS surgery_rows,
    sum(surgery_breach)                         AS surgery_breaches,
    CAST(ROUND(100.0 * sum(surgery_breach)
               / nullif(sum(surgery_measured), 0), 2) AS DECIMAL(9,2))
                                                AS surgery_breach_pct,
    sum(consult_measured)                       AS consult_rows,
    sum(consult_breach)                         AS consult_breaches,
    CAST(ROUND(100.0 * sum(consult_breach)
               / nullif(sum(consult_measured), 0), 2) AS DECIMAL(9,2))
                                                AS consult_breach_pct,
    CASE WHEN sum(surgery_measured) >= min_measured_rows() THEN 1 ELSE 0 END
                                                AS meets_min_rows
FROM facility_lines
GROUP BY procedure
ORDER BY procedure;

-- The single worst measured line per facility, picked by longest published
-- surgery_median. The tie-break runs procedure then period, so the pick is
-- the same on every engine and every run.
CREATE OR REPLACE TABLE facility_worst_line AS
SELECT facility, procedure, period, year_quarter_index,
       surgery_median, surgery_90th, surgery_tail_gap,
       consult_median, consult_90th, consult_tail_gap
FROM (
    SELECT *,
           row_number() OVER (
               PARTITION BY facility
               ORDER BY surgery_median DESC, procedure, period
           ) AS rn
    FROM facility_lines
    WHERE surgery_measured = 1
)
WHERE rn = 1
ORDER BY facility;

-- The same pick per procedure, tie-broken facility then period.
CREATE OR REPLACE TABLE procedure_worst_line AS
SELECT procedure, facility, period, year_quarter_index,
       surgery_median, surgery_90th, surgery_tail_gap,
       consult_median, consult_90th, consult_tail_gap
FROM (
    SELECT *,
           row_number() OVER (
               PARTITION BY procedure
               ORDER BY surgery_median DESC, facility, period
           ) AS rn
    FROM facility_lines
    WHERE surgery_measured = 1
)
WHERE rn = 1
ORDER BY procedure;

-- The longest published facility surgery medians in the snapshot, line by
-- line. Ranked on the measure, then facility, procedure, period.
CREATE OR REPLACE TABLE worst_lines AS
SELECT *
FROM (
    SELECT
        row_number() OVER (
            ORDER BY surgery_median DESC, facility, procedure, period
        ) AS rnk,
        zone, facility, procedure, period, year_quarter_index,
        surgery_median, surgery_90th, surgery_tail_gap,
        consult_median, consult_90th, consult_tail_gap,
        surgery_measured, surgery_breach
    FROM facility_lines
    WHERE surgery_measured = 1
)
WHERE rnk <= worst_lines_shown()
ORDER BY rnk;

-- Quarter-over-quarter movement in the published provincial reference series.
-- These are the source's own 'Total' / 'Provincial' rows, kept out of every
-- facility aggregate above. The quarter-over-quarter step uses
-- year_quarter_index, so the 2023_q4 to 2024_q1 step is index 8096 to 8097
-- like any other.
CREATE OR REPLACE TABLE provincial_quarter AS
SELECT
    period,
    year,
    quarter,
    year_quarter_index,
    count(*)                                    AS lines_total,
    sum(surgery_measured)                       AS surgery_rows,
    sum(surgery_breach)                         AS surgery_breaches,
    CAST(ROUND(100.0 * sum(surgery_breach)
               / nullif(sum(surgery_measured), 0), 2) AS DECIMAL(9,2))
                                                AS surgery_breach_pct,
    sum(consult_measured)                       AS consult_rows,
    sum(consult_breach)                         AS consult_breaches,
    CAST(ROUND(100.0 * sum(consult_breach)
               / nullif(sum(consult_measured), 0), 2) AS DECIMAL(9,2))
                                                AS consult_breach_pct
FROM provincial_lines
GROUP BY period, year, quarter, year_quarter_index
ORDER BY year_quarter_index, period;

CREATE OR REPLACE TABLE provincial_worst_line AS
SELECT period, procedure, surgery_median, surgery_90th, surgery_tail_gap,
       consult_median, consult_90th, consult_tail_gap
FROM (
    SELECT *,
           row_number() OVER (
               PARTITION BY period
               ORDER BY surgery_median DESC, procedure
           ) AS rn
    FROM provincial_lines
    WHERE surgery_measured = 1
)
WHERE rn = 1
ORDER BY period;

CREATE OR REPLACE TABLE provincial_trend AS
SELECT
    q.*,
    CAST(q.surgery_breach_pct
         - lag(q.surgery_breach_pct) OVER (ORDER BY q.year_quarter_index)
         AS DECIMAL(9,2))                       AS qoq_surgery_breach_pct,
    w.procedure                                 AS worst_procedure,
    w.surgery_median                            AS worst_surgery_median,
    w.surgery_90th                              AS worst_surgery_90th,
    w.surgery_tail_gap                          AS worst_surgery_tail_gap,
    w.consult_median                            AS worst_consult_median,
    w.consult_90th                              AS worst_consult_90th,
    w.consult_tail_gap                          AS worst_consult_tail_gap
FROM provincial_quarter q
LEFT JOIN provincial_worst_line w USING (period)
ORDER BY q.year_quarter_index, q.period;

-- The sectioned result. Sections, in file order:
--   constants        the four named constants this build declares
--   coverage         what the analysis grain contains
--   exclusions       every row class held out, plus the blank-column counts
--   breach_summary   the two headline breach rates and the tail-gap spread
--   worst_facilities every facility ranked by surgery breach rate
--   worst_procedures every procedure ranked by surgery breach rate
--   worst_lines      the longest published facility surgery medians
--   provincial_trend the published provincial series, quarter over quarter
--
-- Column meaning is fixed across sections. The six line-level columns
-- (surgery_median through consult_tail_gap) always describe ONE published
-- line. In the grouped sections that line is the group's worst measured line
-- by surgery_median, named by the facility, procedure, and period columns on
-- the same row.
CREATE OR REPLACE TABLE wait_time_sla AS
WITH sections AS (

    SELECT
        1 AS section_order, 'constants' AS section, 1 AS rank,
        'surgery_target_days' AS measure,
        '' AS zone, '' AS facility, '' AS procedure, '' AS period,
        CAST(NULL AS INTEGER) AS year_quarter_index,
        CAST(surgery_target_days() AS BIGINT) AS value,
        CAST(NULL AS BIGINT) AS surgery_rows,
        CAST(NULL AS BIGINT) AS surgery_breaches,
        CAST(NULL AS DECIMAL(9,2)) AS surgery_breach_pct,
        CAST(NULL AS BIGINT) AS consult_rows,
        CAST(NULL AS BIGINT) AS consult_breaches,
        CAST(NULL AS DECIMAL(9,2)) AS consult_breach_pct,
        CAST(NULL AS DECIMAL(9,2)) AS qoq_surgery_breach_pct,
        CAST(NULL AS INTEGER) AS meets_min_rows,
        CAST(NULL AS INTEGER) AS surgery_median,
        CAST(NULL AS INTEGER) AS surgery_90th,
        CAST(NULL AS INTEGER) AS surgery_tail_gap,
        CAST(NULL AS INTEGER) AS consult_median,
        CAST(NULL AS INTEGER) AS consult_90th,
        CAST(NULL AS INTEGER) AS consult_tail_gap

    UNION ALL SELECT 1, 'constants', 2, 'consult_target_days',
        '', '', '', '', NULL, CAST(consult_target_days() AS BIGINT),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 1, 'constants', 3, 'min_measured_rows',
        '', '', '', '', NULL, CAST(min_measured_rows() AS BIGINT),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 1, 'constants', 4, 'worst_lines_shown',
        '', '', '', '', NULL, CAST(worst_lines_shown() AS BIGINT),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 2, 'coverage', 1, 'snapshot_rows',
        '', '', '', '', NULL, (SELECT snapshot_rows FROM row_accounting),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 2, 'coverage', 2, 'quarterly_period_rows',
        '', '', '', '', NULL,
        (SELECT count(*) FROM typed_rows WHERE period_class = 'quarterly'),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 2, 'coverage', 3, 'facility_lines_analysed',
        '', '', '', '', NULL, (SELECT count(*) FROM facility_lines),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 2, 'coverage', 4, 'distinct_zones',
        '', '', '', '', NULL, (SELECT count(DISTINCT zone) FROM facility_lines),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 2, 'coverage', 5, 'distinct_facilities',
        '', '', '', '', NULL, (SELECT count(DISTINCT facility) FROM facility_lines),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 2, 'coverage', 6, 'distinct_procedures',
        '', '', '', '', NULL, (SELECT count(DISTINCT procedure) FROM facility_lines),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 2, 'coverage', 7, 'distinct_quarters',
        '', '', '', '', NULL, (SELECT count(DISTINCT period) FROM facility_lines),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 2, 'coverage', 8, 'first_period',
        '', '', '',
        (SELECT min(period) FROM facility_lines),
        (SELECT min(year_quarter_index) FROM facility_lines),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 2, 'coverage', 9, 'last_period',
        '', '', '',
        (SELECT max(period) FROM facility_lines),
        (SELECT max(year_quarter_index) FROM facility_lines),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 1, 'rolling_window_rows_excluded',
        '', '', '', '', NULL, (SELECT rolling_rows FROM row_accounting),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 2, 'provincial_rollup_rows_excluded',
        '', '', '', '', NULL, (SELECT provincial_rows FROM row_accounting),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 3, 'facility_rows_kept',
        '', '', '', '', NULL, (SELECT facility_rows FROM row_accounting),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    -- Must read 0: the three classes above account for every snapshot row.
    UNION ALL SELECT 3, 'exclusions', 4, 'row_class_reconciliation_gap',
        '', '', '', '', NULL,
        (SELECT snapshot_rows - rolling_rows - provincial_rows - facility_rows
         FROM row_accounting),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    -- Must read 0: zone = 'Total' and facility = 'Provincial' always pair up.
    UNION ALL SELECT 3, 'exclusions', 5, 'rollup_marker_mismatches',
        '', '', '', '', NULL, (SELECT rollup_marker_mismatches FROM row_accounting),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 6, 'facility_lines_no_surgery_median',
        '', '', '', '', NULL,
        (SELECT count(*) FROM facility_lines WHERE surgery_measured = 0),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 7, 'facility_lines_no_consult_median',
        '', '', '', '', NULL,
        (SELECT count(*) FROM facility_lines WHERE consult_measured = 0),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 8, 'snapshot_rows_blank_specialty',
        '', '', '', '', NULL,
        (SELECT count(*) FROM typed_rows
          WHERE specialty IS NULL OR trim(specialty) = ''),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 9, 'snapshot_rows_blank_provider',
        '', '', '', '', NULL,
        (SELECT count(*) FROM typed_rows
          WHERE provider IS NULL OR trim(provider) = ''),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 10, 'facility_lines_blank_specialty',
        '', '', '', '', NULL,
        (SELECT count(*) FROM typed_rows
          WHERE period_class = 'quarterly' AND row_class = 'facility'
            AND (specialty IS NULL OR trim(specialty) = '')),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 11, 'facility_lines_blank_provider',
        '', '', '', '', NULL,
        (SELECT count(*) FROM typed_rows
          WHERE period_class = 'quarterly' AND row_class = 'facility'
            AND (provider IS NULL OR trim(provider) = '')),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 12, 'facilities_below_min_measured_rows',
        '', '', '', '', NULL,
        (SELECT count(*) FROM facility_breach WHERE meets_min_rows = 0),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 3, 'exclusions', 13, 'procedures_below_min_measured_rows',
        '', '', '', '', NULL,
        (SELECT count(*) FROM procedure_breach WHERE meets_min_rows = 0),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 4, 'breach_summary', 1, 'surgery_median_vs_target',
        '', '', '', '', NULL, CAST(surgery_target_days() AS BIGINT),
        (SELECT sum(surgery_measured) FROM facility_lines),
        (SELECT sum(surgery_breach) FROM facility_lines),
        (SELECT CAST(ROUND(100.0 * sum(surgery_breach)
                           / nullif(sum(surgery_measured), 0), 2) AS DECIMAL(9,2))
         FROM facility_lines),
        NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 4, 'breach_summary', 2, 'consult_median_vs_target',
        '', '', '', '', NULL, CAST(consult_target_days() AS BIGINT),
        NULL, NULL, NULL,
        (SELECT sum(consult_measured) FROM facility_lines),
        (SELECT sum(consult_breach) FROM facility_lines),
        (SELECT CAST(ROUND(100.0 * sum(consult_breach)
                           / nullif(sum(consult_measured), 0), 2) AS DECIMAL(9,2))
         FROM facility_lines),
        NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 4, 'breach_summary', 3, 'surgery_tail_gap_days_median',
        '', '', '', '', NULL,
        (SELECT quantile_disc(surgery_tail_gap, 0.5) FROM facility_lines
          WHERE surgery_tail_gap IS NOT NULL),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 4, 'breach_summary', 4, 'surgery_tail_gap_days_max',
        '', '', '', '', NULL,
        (SELECT max(surgery_tail_gap) FROM facility_lines),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 4, 'breach_summary', 5, 'consult_tail_gap_days_median',
        '', '', '', '', NULL,
        (SELECT quantile_disc(consult_tail_gap, 0.5) FROM facility_lines
          WHERE consult_tail_gap IS NOT NULL),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL SELECT 4, 'breach_summary', 6, 'consult_tail_gap_days_max',
        '', '', '', '', NULL,
        (SELECT max(consult_tail_gap) FROM facility_lines),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL
    SELECT
        5, 'worst_facilities',
        CAST(row_number() OVER (
            ORDER BY b.meets_min_rows DESC,
                     b.surgery_breach_pct DESC NULLS LAST,
                     b.facility
        ) AS INTEGER),
        '',
        b.zone, b.facility, COALESCE(w.procedure, ''), COALESCE(w.period, ''),
        w.year_quarter_index,
        CAST(b.lines_total AS BIGINT),
        b.surgery_rows, b.surgery_breaches, b.surgery_breach_pct,
        b.consult_rows, b.consult_breaches, b.consult_breach_pct,
        NULL, b.meets_min_rows,
        w.surgery_median, w.surgery_90th, w.surgery_tail_gap,
        w.consult_median, w.consult_90th, w.consult_tail_gap
    FROM facility_breach b
    LEFT JOIN facility_worst_line w USING (facility)

    UNION ALL
    SELECT
        6, 'worst_procedures',
        CAST(row_number() OVER (
            ORDER BY b.meets_min_rows DESC,
                     b.surgery_breach_pct DESC NULLS LAST,
                     b.procedure
        ) AS INTEGER),
        '',
        '', COALESCE(w.facility, ''), b.procedure, COALESCE(w.period, ''),
        w.year_quarter_index,
        CAST(b.lines_total AS BIGINT),
        b.surgery_rows, b.surgery_breaches, b.surgery_breach_pct,
        b.consult_rows, b.consult_breaches, b.consult_breach_pct,
        NULL, b.meets_min_rows,
        w.surgery_median, w.surgery_90th, w.surgery_tail_gap,
        w.consult_median, w.consult_90th, w.consult_tail_gap
    FROM procedure_breach b
    LEFT JOIN procedure_worst_line w USING (procedure)

    UNION ALL
    SELECT
        7, 'worst_lines', CAST(rnk AS INTEGER), '',
        zone, facility, procedure, period, year_quarter_index,
        NULL,
        CAST(surgery_measured AS BIGINT), CAST(surgery_breach AS BIGINT),
        NULL, NULL, NULL, NULL, NULL, NULL,
        surgery_median, surgery_90th, surgery_tail_gap,
        consult_median, consult_90th, consult_tail_gap
    FROM worst_lines

    UNION ALL
    SELECT
        8, 'provincial_trend',
        CAST(row_number() OVER (ORDER BY year_quarter_index, period) AS INTEGER),
        '',
        'Total', 'Provincial', COALESCE(worst_procedure, ''), period,
        year_quarter_index,
        CAST(lines_total AS BIGINT),
        surgery_rows, surgery_breaches, surgery_breach_pct,
        consult_rows, consult_breaches, consult_breach_pct,
        qoq_surgery_breach_pct, NULL,
        worst_surgery_median, worst_surgery_90th, worst_surgery_tail_gap,
        worst_consult_median, worst_consult_90th, worst_consult_tail_gap
    FROM provincial_trend
)
SELECT * FROM sections
ORDER BY section_order, rank, facility, procedure, period;

-- BI mart: the facility grain, one row per published facility-procedure-quarter
-- line, with the targets carried as columns so neither BI face hardcodes a
-- threshold and neither recomputes a median. Provincial rollup rows are not in
-- here at all, so no BI aggregate can double count them by accident.
CREATE OR REPLACE TABLE mart_wait_times AS
SELECT
    period,
    year,
    quarter,
    year_quarter_index,
    zone,
    facility,
    procedure,
    consult_median,
    consult_90th,
    consult_tail_gap,
    surgery_median,
    surgery_90th,
    surgery_tail_gap,
    surgery_target_days() AS surgery_target_days,
    consult_target_days() AS consult_target_days,
    surgery_measured,
    surgery_breach,
    consult_measured,
    consult_breach
FROM facility_lines
ORDER BY facility, procedure, year_quarter_index, period;

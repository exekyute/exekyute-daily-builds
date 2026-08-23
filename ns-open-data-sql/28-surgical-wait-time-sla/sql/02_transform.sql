-- 02_transform.sql
-- Typing, row classification, and the derived columns. Deterministic rules:
--
--   * period_class: a period matching YYYY_qN is a quarterly reporting period.
--     Everything else ('12month_rolling', '3month_rolling') is a rolling
--     window published alongside the quarters. Rolling windows overlap the
--     quarters and each other, so they are a separate reporting product, not
--     extra quarters. They are excluded from every aggregate here and counted
--     in the exclusions section.
--   * row_class: inside the quarterly periods, zone = 'Total' with facility =
--     'Provincial' marks a published provincial rollup line. Those rollups
--     repeat the same waits already counted at the facilities, so including
--     them in a facility or zone aggregate double counts. They are excluded
--     from the facility grain and used only as the published provincial
--     reference series in 03_analysis.sql.
--   * procedure, facility, zone: trimmed, runs of spaces collapsed. The
--     source writes 20 procedure labels with a double space before a bracket
--     ('Back Surgery  (Adult)'). Collapsing merges no two distinct labels:
--     130 distinct raw labels stay 130 after the collapse.
--   * the four published measures cast to INTEGER. A value that will not cast
--     fails the run rather than becoming NULL silently. A genuinely absent
--     measure (the source leaves the field empty when a line has too few
--     cases to publish) stays NULL and is counted, never treated as a zero.
--   * year_quarter_index = year * 4 + quarter. A sortable integer whose
--     previous quarter is always index - 1, including across a year boundary.
--     The Power BI prior-quarter measure indexes on this column.
--   * tail gaps: surgery_90th - surgery_median and consult_90th -
--     consult_median, one column per measure pair. Both are NULL when either
--     side of their pair is absent.

CREATE OR REPLACE TABLE typed_rows AS
WITH cast_rows AS (
    SELECT
        trim(period) AS period,
        CASE
            WHEN regexp_matches(trim(period), '^[0-9]{4}_q[1-4]$')
            THEN 'quarterly'
            ELSE 'rolling'
        END AS period_class,
        specialty,
        provider,
        regexp_replace(trim(procedure), ' +', ' ', 'g') AS procedure,
        regexp_replace(trim(zone), ' +', ' ', 'g')      AS zone,
        regexp_replace(trim(facility), ' +', ' ', 'g')  AS facility,
        CAST(year AS INTEGER)           AS year,
        CAST(quarter AS INTEGER)        AS quarter,
        CAST(consult_median AS INTEGER) AS consult_median,
        CAST(consult_90th AS INTEGER)   AS consult_90th,
        CAST(surgery_median AS INTEGER) AS surgery_median,
        CAST(surgery_90th AS INTEGER)   AS surgery_90th
    FROM raw_wait_times
)
SELECT
    period,
    period_class,
    CASE
        WHEN period_class = 'rolling' THEN 'rolling'
        WHEN zone = 'Total' AND facility = 'Provincial' THEN 'provincial'
        ELSE 'facility'
    END AS row_class,
    specialty,
    provider,
    procedure,
    zone,
    facility,
    year,
    quarter,
    CASE
        WHEN year IS NOT NULL AND quarter IS NOT NULL
        THEN year * 4 + quarter
    END AS year_quarter_index,
    consult_median,
    consult_90th,
    consult_90th - consult_median AS consult_tail_gap,
    surgery_median,
    surgery_90th,
    surgery_90th - surgery_median AS surgery_tail_gap
FROM cast_rows;

-- Facility-grain analysis table: quarterly periods, facility rows only.
-- Breach flags compare a published median against its own named target.
-- measured is 1 when the source published that median and 0 when it did not,
-- so a breach rate always divides by lines that actually carry a number.
CREATE OR REPLACE TABLE facility_lines AS
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
    CASE WHEN surgery_median IS NULL THEN 0 ELSE 1 END AS surgery_measured,
    CASE WHEN consult_median IS NULL THEN 0 ELSE 1 END AS consult_measured,
    CASE
        WHEN surgery_median IS NULL THEN 0
        WHEN surgery_median > surgery_target_days() THEN 1
        ELSE 0
    END AS surgery_breach,
    CASE
        WHEN consult_median IS NULL THEN 0
        WHEN consult_median > consult_target_days() THEN 1
        ELSE 0
    END AS consult_breach
FROM typed_rows
WHERE period_class = 'quarterly'
  AND row_class = 'facility';

-- The published provincial reference series: same quarterly periods, the
-- rollup lines only. Never unioned into facility_lines; it exists so the
-- quarter-over-quarter trend reads the province's own published numbers
-- instead of an average of facility numbers.
CREATE OR REPLACE TABLE provincial_lines AS
SELECT
    period,
    year,
    quarter,
    year_quarter_index,
    procedure,
    consult_median,
    consult_90th,
    consult_tail_gap,
    surgery_median,
    surgery_90th,
    surgery_tail_gap,
    CASE WHEN surgery_median IS NULL THEN 0 ELSE 1 END AS surgery_measured,
    CASE WHEN consult_median IS NULL THEN 0 ELSE 1 END AS consult_measured,
    CASE
        WHEN surgery_median IS NULL THEN 0
        WHEN surgery_median > surgery_target_days() THEN 1
        ELSE 0
    END AS surgery_breach,
    CASE
        WHEN consult_median IS NULL THEN 0
        WHEN consult_median > consult_target_days() THEN 1
        ELSE 0
    END AS consult_breach
FROM typed_rows
WHERE period_class = 'quarterly'
  AND row_class = 'provincial';

-- Row accounting. Every snapshot row lands in exactly one class, so the three
-- class counts must add back to the snapshot row count. The reconciliation is
-- exported in the exclusions section rather than asserted silently here.
CREATE OR REPLACE TABLE row_accounting AS
SELECT
    (SELECT count(*) FROM raw_wait_times)                                  AS snapshot_rows,
    (SELECT count(*) FROM typed_rows WHERE row_class = 'rolling')          AS rolling_rows,
    (SELECT count(*) FROM typed_rows WHERE row_class = 'provincial')       AS provincial_rows,
    (SELECT count(*) FROM typed_rows WHERE row_class = 'facility')         AS facility_rows,
    -- Integrity check on the rollup marker: zone = 'Total' and facility =
    -- 'Provincial' should always travel together. A nonzero count here means
    -- the rollup rule needs revisiting before the exclusion can be trusted.
    (SELECT count(*) FROM typed_rows
      WHERE (zone = 'Total') <> (facility = 'Provincial'))                 AS rollup_marker_mismatches;

-- 03_analysis.sql
-- Builds every compliance breakdown, then stacks them into one sectioned
-- result table (water_compliance). Percentages are display values rounded
-- to two decimals after an exact division on DECIMAL inputs.
--
-- Every ranked query ends in a total order: the sort finishes on a column
-- that is unique within the section (analyte, location_id, or the pair of
-- the two), so no two rows can tie into an undefined order and the file is
-- byte-stable across engine versions and thread counts.

-- ROW_CLASS_ORDER. The fixed list of buckets 02_transform.sql can put a row
-- in, with the order they are reported in. Declaring the list here rather
-- than reading it back out of the data means the ledger prints every class
-- including the ones that caught nothing, which is the point of a ledger.
CREATE OR REPLACE TABLE const_row_class (class_order INTEGER, row_class VARCHAR);
INSERT INTO const_row_class VALUES
    (1, 'analyte_not_in_scope'),
    (2, 'wrong_fraction'),
    (3, 'quality_control'),
    (4, 'unaccepted_status'),
    (5, 'wrong_unit'),
    (6, 'malformed'),
    (7, 'non_detect_minimum_direction'),
    (8, 'evaluated');

-- Counts per class, with the zero-count classes carried through.
CREATE OR REPLACE TABLE class_counts AS
SELECT
    k.class_order,
    k.row_class,
    COALESCE(c.n, 0) AS n_rows
FROM const_row_class k
LEFT JOIN (
    SELECT row_class, count(*) AS n FROM scored_results GROUP BY row_class
) c USING (row_class);

-- The evaluated set: every row that was actually compared against a
-- guideline. Every pass rate below is built from this table and nothing
-- else.
CREATE OR REPLACE TABLE evaluated_results AS
SELECT * FROM scored_results WHERE row_class = 'evaluated';

-- Network-wide totals.
CREATE OR REPLACE TABLE overall_totals AS
SELECT
    count(*)                                             AS n_samples,
    sum(is_pass)                                         AS n_passing,
    CAST(ROUND(sum(is_pass) * 100.0 / count(*), 2) AS DECIMAL(9,2))  AS pass_pct,
    sum(CASE WHEN is_non_detect THEN 1 ELSE 0 END)       AS n_non_detect,
    CAST(ROUND(sum(CASE WHEN is_non_detect THEN 1 ELSE 0 END) * 100.0
               / count(*), 2) AS DECIMAL(9,2))           AS nondetect_pct,
    COALESCE(sum(is_censored_above), 0)                  AS n_censored_above,
    sum(is_limit_unknown)                                AS n_limit_unknown,
    min(sample_date)                                     AS first_sample_date,
    max(sample_date)                                     AS last_sample_date,
    date_diff('day', max(sample_date), (SELECT pull_date FROM const_run))
                                                         AS days_since_last_sample
FROM evaluated_results;

-- Per-analyte compliance. Driven off the guideline constants rather than
-- off the data, so an analyte that ends up with no evaluated sample still
-- gets a row instead of disappearing. Ranked worst pass rate first, ties
-- broken on analyte, which is unique.
CREATE OR REPLACE TABLE analyte_compliance AS
SELECT
    row_number() OVER (ORDER BY pass_pct NULLS LAST, analyte) AS rnk,
    *
FROM (
    SELECT
        g.analyte,
        g.direction,
        g.threshold,
        g.guideline_unit,
        count(e.analyte)                                     AS n_samples,
        COALESCE(sum(e.is_pass), 0)                          AS n_passing,
        CASE WHEN count(e.analyte) > 0 THEN CAST(ROUND(
            sum(e.is_pass) * 100.0 / count(e.analyte), 2) AS DECIMAL(9,2)) END
                                                             AS pass_pct,
        COALESCE(sum(CASE WHEN e.is_non_detect THEN 1 ELSE 0 END), 0)
                                                             AS n_non_detect,
        CASE WHEN count(e.analyte) > 0 THEN CAST(ROUND(
            sum(CASE WHEN e.is_non_detect THEN 1 ELSE 0 END) * 100.0
            / count(e.analyte), 2) AS DECIMAL(9,2)) END      AS nondetect_pct,
        COALESCE(sum(e.is_censored_above), 0)                AS n_censored_above,
        min(e.sample_date)                                   AS first_sample_date,
        max(e.sample_date)                                   AS last_sample_date,
        date_diff('day', max(e.sample_date), (SELECT pull_date FROM const_run))
                                                             AS days_since_last_sample
    FROM const_analyte_guideline g
    LEFT JOIN evaluated_results e
      ON e.analyte = g.analyte
    GROUP BY g.analyte, g.direction, g.threshold, g.guideline_unit
);

-- Per-location compliance, ranked worst pass rate first, ties broken on
-- location_id, which is unique. Rank 1 is the worst-performing location.
CREATE OR REPLACE TABLE location_compliance AS
SELECT
    row_number() OVER (ORDER BY pass_pct NULLS LAST, location_id) AS rnk,
    *
FROM (
    SELECT
        location_id,
        location,
        count(*)                                             AS n_samples,
        sum(is_pass)                                         AS n_passing,
        CAST(ROUND(sum(is_pass) * 100.0 / count(*), 2) AS DECIMAL(9,2))
                                                             AS pass_pct,
        sum(CASE WHEN is_non_detect THEN 1 ELSE 0 END)       AS n_non_detect,
        CAST(ROUND(sum(CASE WHEN is_non_detect THEN 1 ELSE 0 END) * 100.0
                   / count(*), 2) AS DECIMAL(9,2))           AS nondetect_pct,
        COALESCE(sum(is_censored_above), 0)                  AS n_censored_above,
        count(DISTINCT analyte)                              AS n_analytes,
        min(sample_date)                                     AS first_sample_date,
        max(sample_date)                                     AS last_sample_date,
        date_diff('day', max(sample_date), (SELECT pull_date FROM const_run))
                                                             AS days_since_last_sample
    FROM evaluated_results
    GROUP BY location_id, location
);

-- The analyte-by-location matrix: one cell per pair that has at least one
-- evaluated sample. This is the grid the Power BI matrix mirrors. Ordered
-- by location then analyte, a pair that is unique by construction.
CREATE OR REPLACE TABLE analyte_location AS
SELECT
    row_number() OVER (ORDER BY location_id, analyte) AS rnk,
    *
FROM (
    SELECT
        location_id,
        location,
        analyte,
        count(*)                                             AS n_samples,
        sum(is_pass)                                         AS n_passing,
        CAST(ROUND(sum(is_pass) * 100.0 / count(*), 2) AS DECIMAL(9,2))
                                                             AS pass_pct,
        sum(CASE WHEN is_non_detect THEN 1 ELSE 0 END)       AS n_non_detect,
        COALESCE(sum(is_censored_above), 0)                  AS n_censored_above,
        min(sample_date)                                     AS first_sample_date,
        max(sample_date)                                     AS last_sample_date
    FROM evaluated_results
    GROUP BY location_id, location, analyte
);

-- The worst cells in that matrix: every analyte-and-location pair that
-- breached its guideline at least once, worst pass rate first, capped at
-- 15. The pass_pct < 100 filter is what keeps the section meaningful:
-- padding it out to a fixed 15 rows would fill most of the list with cells
-- that never failed and label them "worst". Ordered by pass rate then by
-- the unique location_id and analyte pair, so the cap is deterministic if a
-- later snapshot ever pushes past it.
CREATE OR REPLACE TABLE worst_cells AS
SELECT
    row_number() OVER (ORDER BY pass_pct, location_id, analyte) AS rnk,
    location_id, location, analyte, n_samples, n_passing, pass_pct,
    n_non_detect, n_censored_above
FROM analyte_location
WHERE pass_pct < 100
QUALIFY row_number() OVER (ORDER BY pass_pct, location_id, analyte) <= 15;

-- The sectioned result. Sections, in file order:
--   summary             the headline figures
--   row_ledger          every published row accounted for, class by class
--   analyte_compliance  pass rate per analyte, worst first
--   location_compliance pass rate per monitoring location, worst first
--   analyte_location    the full analyte-by-location matrix
--   worst_cells         the 15 worst cells in that matrix
CREATE OR REPLACE TABLE water_compliance AS
WITH sections AS (

    SELECT
        1 AS section_order, 'summary' AS section, 1 AS rank,
        'evaluated_samples' AS measure,
        '' AS analyte, '' AS location_id, '' AS location,
        '' AS direction,
        CAST(NULL AS DECIMAL(12,3)) AS threshold,
        '' AS guideline_unit,
        n_samples, n_passing, pass_pct, n_non_detect, nondetect_pct,
        n_censored_above, first_sample_date, last_sample_date,
        days_since_last_sample
    FROM overall_totals

    UNION ALL

    SELECT 1, 'summary', 2, 'analytes_in_scope', '', '', '', '', NULL, '',
        (SELECT count(*) FROM const_analyte_guideline),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT 1, 'summary', 3, 'monitoring_locations', '', '', '', '', NULL, '',
        (SELECT count(*) FROM location_compliance),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT 1, 'summary', 4, 'duplicate_rows_removed', '', '', '', '', NULL, '',
        (SELECT duplicate_rows_removed FROM snapshot_counts),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT 1, 'summary', 5, 'quality_control_rows_excluded', '', '', '', '', NULL, '',
        (SELECT n_rows FROM class_counts WHERE row_class = 'quality_control'),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT 1, 'summary', 6, 'non_detects_with_unknown_limit', '', '', '', '', NULL, '',
        (SELECT n_limit_unknown FROM overall_totals),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    -- The ledger. Rows 1 to 3 describe the snapshot and the duplicate
    -- collapse; rows 4 to 11 are the eight mutually exclusive classes every
    -- deduped row lands in; rows 12 and 13 are the two arithmetic checks
    -- that make "no row was silently dropped" a figure in the file rather
    -- than a claim in the README.
    UNION ALL

    SELECT 2, 'row_ledger', 1, 'raw_rows_in_snapshot', '', '', '', '', NULL, '',
        (SELECT raw_rows FROM snapshot_counts),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT 2, 'row_ledger', 2, 'exact_duplicate_rows_removed', '', '', '', '', NULL, '',
        (SELECT duplicate_rows_removed FROM snapshot_counts),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT 2, 'row_ledger', 3, 'rows_after_dedup', '', '', '', '', NULL, '',
        (SELECT deduped_rows FROM snapshot_counts),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT 2, 'row_ledger', 3 + class_order, 'class_' || row_class,
        '', '', '', '', NULL, '',
        n_rows, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
    FROM class_counts

    UNION ALL

    SELECT 2, 'row_ledger', 12, 'check_classes_equal_rows_after_dedup',
        '', '', '', '', NULL, '',
        (SELECT sum(n_rows) FROM class_counts),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT 2, 'row_ledger', 13, 'check_dedup_plus_duplicates_equal_raw',
        '', '', '', '', NULL, '',
        (SELECT deduped_rows + duplicate_rows_removed FROM snapshot_counts),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        3, 'analyte_compliance', rnk, '',
        analyte, '', '', direction, threshold, guideline_unit,
        n_samples, n_passing, pass_pct, n_non_detect, nondetect_pct,
        n_censored_above, first_sample_date, last_sample_date,
        days_since_last_sample
    FROM analyte_compliance

    UNION ALL

    SELECT
        4, 'location_compliance', rnk, '',
        '', location_id, location, '', NULL, '',
        n_samples, n_passing, pass_pct, n_non_detect, nondetect_pct,
        n_censored_above, first_sample_date, last_sample_date,
        days_since_last_sample
    FROM location_compliance

    UNION ALL

    SELECT
        5, 'analyte_location', rnk, '',
        analyte, location_id, location, '', NULL, '',
        n_samples, n_passing, pass_pct, n_non_detect, NULL,
        n_censored_above, first_sample_date, last_sample_date, NULL
    FROM analyte_location

    UNION ALL

    SELECT
        6, 'worst_cells', rnk, '',
        analyte, location_id, location, '', NULL, '',
        n_samples, n_passing, pass_pct, n_non_detect, NULL,
        n_censored_above, NULL, NULL, NULL
    FROM worst_cells
)
SELECT * FROM sections
ORDER BY section_order, rank;

-- BI mart: every deduped row whose analyte is in scope, carrying the class
-- that decided its fate and the flags 02_transform.sql already computed.
-- Power BI aggregates those flags; it never re-applies a threshold, so a
-- floating-point import cannot move a pass rate away from the golden.
-- Out-of-scope analytes are left out (they have no guideline to report
-- against); the ledger in the result file is where they are accounted for.
--
-- The primary key is the real sample key. If a later snapshot ever
-- publishes two different results for one analyte at one location, date,
-- time, and fraction, this insert fails loudly instead of quietly counting
-- the visit twice.
CREATE OR REPLACE TABLE mart_water (
    sample_date          DATE,
    sample_time          VARCHAR,
    sample_year          INTEGER,
    location_id          VARCHAR,
    location             VARCHAR,
    analyte              VARCHAR,
    sample_fraction      VARCHAR,
    result_unit          VARCHAR,
    result_value         DECIMAL(18,6),
    guideline_unit       VARCHAR,
    guideline_threshold  DECIMAL(12,3),
    guideline_direction  VARCHAR,
    row_class            VARCHAR,
    is_evaluated         INTEGER,
    is_pass              INTEGER,
    is_non_detect        INTEGER,
    is_censored_above    INTEGER,
    PRIMARY KEY (location_id, analyte, sample_fraction, sample_date, sample_time)
);

INSERT INTO mart_water
SELECT
    sample_date,
    sample_time,
    CAST(year(sample_date) AS INTEGER)                       AS sample_year,
    location_id,
    location,
    analyte,
    sample_fraction,
    result_unit,
    result_value,
    guideline_unit,
    threshold                                                AS guideline_threshold,
    direction                                                AS guideline_direction,
    row_class,
    CASE WHEN row_class = 'evaluated' THEN 1 ELSE 0 END       AS is_evaluated,
    is_pass,
    CASE WHEN is_non_detect THEN 1 ELSE 0 END                 AS is_non_detect,
    is_censored_above
FROM scored_results
WHERE row_class <> 'analyte_not_in_scope';

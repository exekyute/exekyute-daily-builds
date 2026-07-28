-- 02_transform.sql
-- Turns the raw landing table into one classified row per published record.
-- Nothing is thrown away here. Every row leaves this file carrying a
-- row_class that says exactly why it will or will not be compared against a
-- guideline, and 03_analysis.sql adds the class counts back up to prove the
-- ledger balances.
--
-- The steps, in order:
--   1. collapse byte-identical duplicate records and count them
--   2. type and normalize the fields that the rules read
--   3. pick one display name per monitoring location
--   4. attach the guideline, convert the unit, and assign the row_class
--   5. apply the pass rule and the detection-limit diagnostic

-- Step 1: exact duplicates.
-- The published extract repeats records. 18,274 of the 38,143 rows are
-- byte-identical copies of another row across all 26 columns, right down to
-- the laboratory sample id, so they are one lab result published more than
-- once, not two measurements. Left in place they inflate every sample
-- count and re-weight every pass rate toward whichever results happen to
-- be repeated. SELECT DISTINCT collapses them; both counts survive into
-- the ledger in the output, so a reader can watch the collapse happen.
CREATE OR REPLACE TABLE dedup_results AS
SELECT DISTINCT * FROM raw_results;

CREATE OR REPLACE TABLE snapshot_counts AS
SELECT
    (SELECT count(*) FROM raw_results)                                   AS raw_rows,
    (SELECT count(*) FROM dedup_results)                                 AS deduped_rows,
    (SELECT count(*) FROM raw_results) - (SELECT count(*) FROM dedup_results)
                                                                         AS duplicate_rows_removed;

-- Step 2: typing and normalization.
--   * unit text is trimmed and lowercased, which is the whole normalization
--     needed here: the snapshot writes the same unit as both 'mg/L' and
--     'mg/l', and as both 'ug/l' and 'ug/L'. Matching the raw string would
--     quietly strand the minority spelling in the wrong_unit bucket.
--   * a blank or missing sample fraction becomes the literal label
--     '(not stated)' so it joins and groups like any other fraction instead
--     of vanishing on a NULL comparison.
--   * result status gets the same '(not stated)' treatment, so a row with
--     no status is refused by the allowlist instead of slipping past it.
--   * values and detection limits use TRY_CAST. A value that will not cast
--     becomes NULL here and is classified as malformed in step 4, where it
--     is counted; it never reaches a comparison.
--   * the published timestamp is 'YYYY-MM-DDTHH:MM:SS.mmm'; the date part
--     is cast to DATE and the clock time is kept separately, because a
--     location can be sampled twice on one date and the pair of visits has
--     to stay distinguishable.
CREATE OR REPLACE TABLE typed_results AS
SELECT
    monitoringlocationid                                              AS location_id,
    trim(monitoringlocationwaterbody)                                 AS location_raw,
    trim(characteristicname)                                          AS analyte,
    COALESCE(NULLIF(trim(resultsamplefraction), ''), '(not stated)')  AS sample_fraction,
    trim(activitytype)                                                AS activitytype,
    COALESCE(NULLIF(trim(resultstatusid), ''), '(not stated)')        AS result_status,
    lower(trim(resultunit))                                           AS result_unit,
    CAST(substr(activitystartdate, 1, 10) AS DATE)                    AS sample_date,
    trim(activitystarttime)                                           AS sample_time,
    TRY_CAST(resultvalue AS DECIMAL(18,6))                            AS result_value_raw,
    (resultdetectioncondition IS NOT NULL
     AND trim(resultdetectioncondition) <> '')                        AS is_non_detect,
    TRY_CAST(resultdetectionquantitationlimitmeasure AS DECIMAL(18,6)) AS detection_limit_raw,
    lower(trim(resultdetectionquantitationlimitunit))                 AS detection_limit_unit
FROM dedup_results;

-- Step 3: one display name per location id.
-- monitoringlocationwaterbody is the readable river-and-place name and is
-- already one value per id in this snapshot, but the pipeline does not lean
-- on that: it picks the most frequent spelling per id and breaks ties
-- alphabetically, so a later pull that introduces a second spelling still
-- produces one deterministic label instead of splitting the location in
-- two. (monitoringlocationname is not used for this: it is an equipment log
-- code such as 'SHE-HYDROLABREMOVED-0M' and changes 21 times across the 8
-- locations.)
CREATE OR REPLACE TABLE location_display AS
SELECT location_id, location_raw AS location
FROM (
    SELECT
        location_id,
        location_raw,
        row_number() OVER (
            PARTITION BY location_id
            ORDER BY count(*) DESC, location_raw
        ) AS rn
    FROM typed_results
    GROUP BY location_id, location_raw
)
WHERE rn = 1;

-- Step 4: attach the guideline, convert the unit, classify the row.
--
-- The row_class cases are mutually exclusive and evaluated top to bottom,
-- so every row lands in exactly one bucket and the buckets add back up to
-- deduped_rows. Scope comes first, then data defects, so the defect counts
-- describe the analytes actually being measured rather than the whole
-- catalogue:
--
--   analyte_not_in_scope           the analyte has no fixed CCME guideline
--                                  declared in const_analyte_guideline
--   wrong_fraction                 the analyte is in scope but this row is
--                                  the fraction the guideline is not
--                                  written for (dissolved metals, mostly)
--   quality_control                activitytype is not on the allowlist
--   unaccepted_status              resultstatusid is not on the allowlist
--   wrong_unit                     the row's unit has no conversion into
--                                  the unit the guideline is written in
--   malformed                      not flagged as a non-detect and yet has
--                                  no value that will cast to a number
--   non_detect_minimum_direction   a non-detect against a minimum-direction
--                                  guideline: "below the reporting limit"
--                                  cannot be read as meeting a floor, so
--                                  the row is reported on its own and kept
--                                  out of the pass-rate denominator
--   evaluated                      compared against the guideline
--
-- result_value is the reading already converted into the guideline's unit,
-- so every comparison downstream is unit-for-unit. detection_limit gets the
-- same conversion, because the diagnostic in step 5 compares it against the
-- same threshold.
CREATE OR REPLACE TABLE classified_results AS
SELECT
    t.location_id,
    d.location,
    t.analyte,
    t.sample_fraction,
    t.activitytype,
    t.result_status,
    t.sample_date,
    t.sample_time,
    t.result_unit,
    g.guideline_unit,
    g.threshold,
    g.direction,
    t.is_non_detect,
    t.result_value_raw,
    CAST(t.result_value_raw * cv.factor AS DECIMAL(18,6))       AS result_value,
    CAST(t.detection_limit_raw * dcv.factor AS DECIMAL(18,6))   AS detection_limit,
    CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM const_analyte_guideline a WHERE a.analyte = t.analyte
        )                                        THEN 'analyte_not_in_scope'
        WHEN g.analyte IS NULL                   THEN 'wrong_fraction'
        WHEN aat.activitytype IS NULL            THEN 'quality_control'
        WHEN ars.resultstatusid IS NULL          THEN 'unaccepted_status'
        WHEN cv.factor IS NULL                   THEN 'wrong_unit'
        WHEN NOT t.is_non_detect
             AND t.result_value_raw IS NULL      THEN 'malformed'
        WHEN t.is_non_detect
             AND g.direction = 'minimum'         THEN 'non_detect_minimum_direction'
        ELSE 'evaluated'
    END AS row_class
FROM typed_results t
JOIN location_display d
  ON d.location_id = t.location_id
LEFT JOIN const_analyte_guideline g
  ON g.analyte = t.analyte
 AND g.sample_fraction = t.sample_fraction
LEFT JOIN const_accepted_activitytype aat
  ON aat.activitytype = t.activitytype
LEFT JOIN const_accepted_resultstatus ars
  ON ars.resultstatusid = t.result_status
LEFT JOIN const_unit_conversion cv
  ON cv.from_unit = t.result_unit
 AND cv.to_unit = g.guideline_unit
LEFT JOIN const_unit_conversion dcv
  ON dcv.from_unit = t.detection_limit_unit
 AND dcv.to_unit = g.guideline_unit;

-- Step 5: the pass rule and the detection-limit diagnostic.
--
-- PASS RULE, both directions, stated in full:
--   maximum  the guideline is a ceiling. A reading at or below the
--            threshold passes; above it fails. A non-detect passes, because
--            the true concentration is below the reporting limit and a
--            ceiling can only be breached from above.
--   minimum  the guideline is a floor. A reading at or above the threshold
--            passes; below it fails. A non-detect against a floor is not a
--            pass and not a fail: it is excluded in step 4 as
--            non_detect_minimum_direction and reported in its own line, and
--            it never enters the denominator.
-- The boundary is inclusive in both directions because CCME writes these
-- guidelines as values that should not be exceeded and levels that should
-- not fall below, so sitting exactly on the number is not a breach.
--
-- DETECTION-LIMIT DIAGNOSTIC. Counting a non-detect as a pass is only
-- honest when the laboratory could have seen a breach in the first place.
-- If the reporting limit sits above the guideline, "not detected" says
-- nothing about whether the guideline was met, and a pass rate built from
-- those rows is not evidence of compliance. is_censored_above marks exactly
-- those rows so the analyte tables can report how much of a clean-looking
-- pass rate is unconfirmable:
--   1     evaluated non-detect whose converted reporting limit is above
--         the guideline: counted as a pass by the rule above, but the pass
--         cannot be confirmed from this data
--   0     evaluated non-detect whose reporting limit is at or below the
--         guideline: the pass is real
--   NULL  not applicable (a measured value) or not answerable (a non-detect
--         published without a usable reporting limit, counted separately as
--         non-detects with an unknown limit)
CREATE OR REPLACE TABLE scored_results AS
SELECT
    c.*,
    CASE
        WHEN c.row_class <> 'evaluated'                              THEN NULL
        WHEN c.is_non_detect                                         THEN 1
        WHEN c.direction = 'maximum' AND c.result_value <= c.threshold THEN 1
        WHEN c.direction = 'minimum' AND c.result_value >= c.threshold THEN 1
        ELSE 0
    END AS is_pass,
    CASE
        WHEN c.row_class <> 'evaluated' OR NOT c.is_non_detect       THEN NULL
        WHEN c.detection_limit IS NULL                               THEN NULL
        WHEN c.detection_limit > c.threshold                         THEN 1
        ELSE 0
    END AS is_censored_above,
    CASE
        WHEN c.row_class = 'evaluated'
             AND c.is_non_detect
             AND c.detection_limit IS NULL                           THEN 1
        ELSE 0
    END AS is_limit_unknown
FROM classified_results c;

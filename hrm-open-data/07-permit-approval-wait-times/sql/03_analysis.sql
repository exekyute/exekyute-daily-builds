-- 03_analysis.sql
-- The analytical core. One summary table plus a two-line headline.

-- Question A: for each issuance stage and jurisdiction, how many permits are
-- involved, how much total time do they carry, and what does a typical permit's
-- wait look like as both a mean and a median?
-- permit_count uses COUNT(DISTINCT permit_number); the mart grain guarantees one
-- row per permit inside a stage-jurisdiction group, so this is also the row count,
-- and it is the exact denominator the Power BI Avg Duration per Permit measure
-- (DISTINCTCOUNT) uses. median_duration is a deterministic linear-interpolation
-- median (quantile_cont at 0.5), so the golden is stable across runs. A mean and a
-- median differ, so both are reported: the mean drives the waterfall, the median
-- describes the spread the Tableau box plot draws.
CREATE TABLE processing_summary AS
SELECT
  issuance_stage,
  jurisdictional_breakdown,
  COUNT(DISTINCT permit_number)                                 AS permit_count,
  round(SUM(total_duration), 3)                                 AS total_duration,
  round(SUM(total_duration) / COUNT(DISTINCT permit_number), 3) AS avg_duration_per_permit,
  round(quantile_cont(total_duration, 0.5), 3)                  AS median_duration
FROM pt_mart
GROUP BY issuance_stage, jurisdictional_breakdown;

-- Question B (headline): what does Pre Issuance cost a typical permit, and which
-- stage carries the most total duration overall?
-- The stage rollup sums across the jurisdictions within a stage. A permit can
-- appear under more than one jurisdiction inside a stage, so the stage-level
-- distinct permit count is not the sum of the per-jurisdiction counts; that is why
-- the headline reads from a stage rollup, not from processing_summary.
CREATE TABLE headline AS
WITH stage AS (
  SELECT
    issuance_stage,
    SUM(total_duration)           AS stage_duration,
    COUNT(DISTINCT permit_number) AS stage_permits
  FROM pt_mart
  GROUP BY issuance_stage
),
top_stage AS (
  SELECT issuance_stage, stage_duration
  FROM stage
  ORDER BY stage_duration DESC, issuance_stage
  LIMIT 1
)
SELECT
  1 AS ord,
  'Pre Issuance averages '
    || printf('%.3f', (SELECT stage_duration / stage_permits FROM stage WHERE issuance_stage = 'Pre Issuance'))
    || ' days per permit across '
    || (SELECT stage_permits FROM stage WHERE issuance_stage = 'Pre Issuance')
    || ' permits.' AS line
UNION ALL
SELECT
  2 AS ord,
  (SELECT issuance_stage FROM top_stage)
    || ' carries the most total duration: '
    || printf('%.3f', (SELECT stage_duration FROM top_stage))
    || ' days.' AS line
ORDER BY ord;

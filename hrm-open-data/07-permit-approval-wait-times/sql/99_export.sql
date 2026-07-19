-- 99_export.sql
-- Question this step answers: what are the final, deterministic output files?
-- Two writes. The golden summary goes to out/ for the row-for-row verify; the
-- frozen mart goes to bi/exports/ for both BI faces to read. Every COPY ends in an
-- ORDER BY so the row order is stable and the files diff byte for byte.

-- Golden: one row per issuance stage and jurisdiction, heaviest total duration
-- first. The order makes the stage that carries the most time land at the top.
COPY (
  SELECT
    issuance_stage,
    jurisdictional_breakdown,
    permit_count,
    total_duration,
    avg_duration_per_permit,
    median_duration
  FROM processing_summary
  ORDER BY total_duration DESC, issuance_stage, jurisdictional_breakdown
) TO 'out/processing_summary.csv' (HEADER, DELIMITER ',');

-- Frozen mart: the per-permit-per-stage-per-jurisdiction rows both dashboards
-- bind to. Ordered by permit then stage then jurisdiction for a stable snapshot.
COPY (
  SELECT
    permit_number,
    issuance_stage,
    jurisdictional_breakdown,
    total_occurrence,
    total_duration
  FROM pt_mart
  ORDER BY permit_number, issuance_stage, jurisdictional_breakdown
) TO 'bi/exports/mart_processing.csv' (HEADER, DELIMITER ',');

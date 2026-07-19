-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files?
-- Two exports. The audit report goes to out/ for the golden diff; the per-asset
-- mart goes to out/ and run.py copies it into bi/exports/ for the Power BI
-- guide. Both ORDER BY clauses fix the row order completely (uid is unique per
-- asset), which is what makes the output byte-for-byte reproducible.

COPY (
  SELECT section, item, detail, n_assets, n_stale_dormant, pct,
         age_months, last_updated, row_rank
  FROM freshness_audit
  ORDER BY
    CASE section
      WHEN 'overall'         THEN 1
      WHEN 'bucket_summary'  THEN 2
      WHEN 'by_category'     THEN 3
      WHEN 'by_owner'        THEN 4
      WHEN 'worst_offenders' THEN 5
    END,
    row_rank
) TO 'out/freshness_audit.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT uid, name, type, category, owner, last_updated,
         age_months, bucket, bucket_order, stale_or_dormant
  FROM asset_audit
  ORDER BY (age_months IS NULL), age_months DESC, name, uid
) TO 'out/mart_freshness.csv' (HEADER, DELIMITER ',');

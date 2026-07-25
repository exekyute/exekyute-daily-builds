-- 99_export.sql
-- Question this step answers: what are the final, deterministic tables a reader should see?
-- Writes the cohort table to out/coop_longevity.csv (the golden-checked result) and the
-- row-level mart to out/mart_coop_longevity.csv (run.py copies it to bi/exports/ for
-- Power BI). Both ORDER BY clauses make the files byte-for-byte stable across runs.

COPY (
    SELECT
        decade,
        survivors,
        registry_share_pct,
        nonprofit_count,
        forprofit_count,
        nonprofit_share_pct,
        peak_year,
        peak_count,
        oldest_age_years
    FROM cohort_longevity
    ORDER BY decade ASC
) TO 'out/coop_longevity.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        registry_id,
        co_op_name,
        town,
        incorporation_date,
        incorporation_year,
        decade,
        org_form,
        is_nonprofit,
        coop_type,
        age_years
    FROM mart_coop_longevity
    ORDER BY incorporation_date ASC, registry_id ASC
) TO 'out/mart_coop_longevity.csv' (HEADER, DELIMITER ',');

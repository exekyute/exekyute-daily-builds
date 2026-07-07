-- 99_export.sql
-- Writes the deterministic result to out/ for verification. The ORDER BY is
-- repeated here so the exported row order never depends on table scan order:
-- year, then most recipients first, then business type as the tiebreak.

COPY (
    SELECT
        year,
        type_of_business,
        recipients,
        sbig_recipients,
        sbrsg_recipients,
        pct_of_recipients
    FROM grants_by_type_year
    ORDER BY year, recipients DESC, type_of_business
) TO 'out/grants_by_type_year.csv' (HEADER, DELIMITER ',');

-- 99_export.sql
-- Write the audit result and the BI mart. Both exports carry an explicit
-- ORDER BY so the files are byte-stable run to run.

COPY (
    SELECT
        section, rank, measure, fiscal_year, division, program_name, recipient,
        payments, amount, share_pct, cumulative_share_pct, yoy_change, yoy_pct
    FROM funding_audit
    ORDER BY section_order, rank
) TO 'out/funding_audit.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        fiscal_year, fiscal_year_start, division, program_name, recipient,
        payment_amount, is_duplicate_candidate, dup_occurrences
    FROM mart_funding_audit
    ORDER BY fiscal_year_start, division, program_name, recipient,
             payment_amount, dup_occurrences
) TO 'out/mart_funding_audit.csv' (HEADER, DELIMITER ',');

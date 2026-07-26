-- 01_load.sql
-- Load the pinned snapshot. The filename is the pull date; changing the
-- snapshot means re-baselining expected/funding_audit.csv on purpose.

INSERT INTO raw_payments
SELECT department, division, program_name, client_name, payment_amount, fiscal_year
FROM read_csv(
    'data/raw/ns_agriculture-funding_2026-07-06.csv',
    header = true,
    all_varchar = true
);

-- The log at a glance: the months it covers, the customers in it, the rows,
-- and the months a customer skipped between their first payment and their
-- last. A skipped month has no row, so anything that compares a row with the
-- row before it steps straight over it.
SELECT
    MIN(first_month) AS first_month,
    MAX(last_month) AS last_month,
    MAX(last_no) - MIN(first_no) + 1 AS months,
    COUNT(*) AS customers,
    SUM(paid) AS paying_rows,
    SUM(last_no - first_no + 1 - paid) AS skipped_months
FROM (
    SELECT
        customer,
        MIN(month) AS first_month,
        MAX(month) AS last_month,
        MIN(CAST(substr(month, 1, 4) AS INTEGER) * 12 + CAST(substr(month, 6, 2) AS INTEGER) - 1) AS first_no,
        MAX(CAST(substr(month, 1, 4) AS INTEGER) * 12 + CAST(substr(month, 6, 2) AS INTEGER) - 1) AS last_no,
        COUNT(*) AS paid
    FROM mrr
    GROUP BY customer
);

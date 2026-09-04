-- The ledger at a glance, ending on the number everyone checks first: the
-- gap between the recorded closing balance and the closing balance rebuilt
-- from the amounts. On the sample it is 30.00, which sounds like one small
-- slip and is actually two larger errors mostly cancelling. The closing gap
-- dates nothing and hides plenty; the later queries exist to unpack it.
SELECT COUNT(*) AS ledger_rows,
       MIN(txn_date) AS first_date,
       MAX(txn_date) AS last_date,
       (SELECT ROUND(recorded_cents / 100.0, 2) FROM ledger ORDER BY txn_id LIMIT 1) AS opening_balance,
       ROUND(SUM(amount_cents) / 100.0, 2) AS rebuilt_closing,
       (SELECT ROUND(recorded_cents / 100.0, 2) FROM ledger ORDER BY txn_id DESC LIMIT 1) AS recorded_closing,
       ROUND(((SELECT recorded_cents FROM ledger ORDER BY txn_id DESC LIMIT 1) - SUM(amount_cents)) / 100.0, 2) AS closing_gap
FROM ledger;

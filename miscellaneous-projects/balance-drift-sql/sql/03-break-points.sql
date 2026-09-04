-- The rows where the ledger breaks its own arithmetic. Each row is checked
-- locally: the previous recorded balance plus this row's amount must equal
-- this row's recorded balance, LAG doing the looking back, and the first
-- row is measured against a pre-opening balance of zero. These are exactly
-- the rows where 02's drift changes value, but the local check needs no
-- running total and names the error each row introduced on its own.
WITH stepped AS (
    SELECT txn_id,
           txn_date,
           description,
           amount_cents,
           recorded_cents,
           recorded_cents
             - COALESCE(LAG(recorded_cents) OVER (ORDER BY txn_id), 0)
             - amount_cents AS error_cents
    FROM ledger
)
SELECT txn_id,
       txn_date,
       description,
       ROUND(amount_cents / 100.0, 2) AS amount,
       ROUND((recorded_cents - error_cents) / 100.0, 2) AS balance_implied,
       ROUND(recorded_cents / 100.0, 2) AS balance_recorded,
       ROUND(error_cents / 100.0, 2) AS error_introduced
FROM stepped
WHERE error_cents != 0
ORDER BY txn_id;

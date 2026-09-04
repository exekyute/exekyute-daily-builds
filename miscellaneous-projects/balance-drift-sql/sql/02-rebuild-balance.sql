-- The rebuild: the balance each row SHOULD show is the running sum of every
-- amount up to and including it. The opening line is just row one with the
-- opening amount, so no anchor constant is needed anywhere. The drift
-- column is the whole build: zero while the ledger ties, and the moment it
-- moves, the amounts and the recorded balances have stopped agreeing.
SELECT txn_id,
       txn_date,
       description,
       ROUND(amount_cents / 100.0, 2) AS amount,
       ROUND(SUM(amount_cents) OVER (ORDER BY txn_id
                                     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) / 100.0, 2) AS expected_balance,
       ROUND(recorded_cents / 100.0, 2) AS recorded_balance,
       ROUND((recorded_cents - SUM(amount_cents) OVER (ORDER BY txn_id
                                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) / 100.0, 2) AS drift
FROM ledger
ORDER BY txn_id;

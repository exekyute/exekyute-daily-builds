-- Stretches of constant drift, by the flag-then-running-sum island trick: a
-- row opens a new regime when its drift differs from the row before, and
-- the running count of openings numbers the regimes. Every regime after the
-- first is the wake of one break, and the drift it carries is the running
-- total of every error so far, the newest folded in with the rest.
WITH diffs AS (
    SELECT txn_id,
           txn_date,
           recorded_cents - SUM(amount_cents) OVER (ORDER BY txn_id
                                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS drift_cents
    FROM ledger
),
flagged AS (
    SELECT txn_id,
           txn_date,
           drift_cents,
           CASE WHEN LAG(drift_cents) OVER (ORDER BY txn_id) IS NULL
                     OR drift_cents != LAG(drift_cents) OVER (ORDER BY txn_id)
                THEN 1 ELSE 0 END AS opens_regime
    FROM diffs
),
numbered AS (
    SELECT txn_id,
           txn_date,
           drift_cents,
           SUM(opens_regime) OVER (ORDER BY txn_id
                                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS regime
    FROM flagged
)
SELECT regime,
       MIN(txn_id) AS from_txn,
       MAX(txn_id) AS to_txn,
       MIN(txn_date) AS from_date,
       MAX(txn_date) AS to_date,
       COUNT(*) AS ledger_rows,
       ROUND(MIN(drift_cents) / 100.0, 2) AS drift
FROM numbered
GROUP BY regime
ORDER BY regime;

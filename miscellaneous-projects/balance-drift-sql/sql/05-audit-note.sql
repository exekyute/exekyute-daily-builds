-- The line an audit note quotes. The closing drift is the number everyone
-- sees first and it is the least of the story: on the sample, two breaks
-- that partly cancel leave the books 30.00 off while 230.00 of recording
-- error sits inside them. Every field is a scalar subquery over the same
-- rebuilt drift, so a clean ledger prints the verdict and zeros.
WITH diffs AS (
    SELECT txn_id,
           txn_date,
           description,
           recorded_cents - SUM(amount_cents) OVER (ORDER BY txn_id
                                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS drift_cents
    FROM ledger
),
errs AS (
    SELECT txn_id,
           txn_date,
           description,
           drift_cents - COALESCE(LAG(drift_cents) OVER (ORDER BY txn_id), 0) AS error_cents
    FROM diffs
)
SELECT CASE WHEN (SELECT COUNT(*) FROM errs WHERE error_cents != 0) = 0
            THEN 'ledger rebuilds exactly'
            ELSE 'ledger breaks its own arithmetic' END AS verdict,
       (SELECT MIN(txn_id) FROM errs WHERE error_cents != 0) AS first_break_txn,
       (SELECT txn_date FROM errs WHERE error_cents != 0 ORDER BY txn_id LIMIT 1) AS first_break_date,
       (SELECT description FROM errs WHERE error_cents != 0 ORDER BY txn_id LIMIT 1) AS first_break_entry,
       (SELECT ROUND(error_cents / 100.0, 2) FROM errs WHERE error_cents != 0 ORDER BY txn_id LIMIT 1) AS first_error,
       (SELECT COUNT(*) FROM errs WHERE error_cents != 0) AS breaks,
       (SELECT ROUND(COALESCE(SUM(ABS(error_cents)), 0) / 100.0, 2) FROM errs WHERE error_cents != 0) AS total_error,
       (SELECT COUNT(*) FROM diffs WHERE drift_cents != 0) AS rows_off,
       (SELECT ROUND(drift_cents / 100.0, 2) FROM diffs ORDER BY txn_id DESC LIMIT 1) AS closing_drift;

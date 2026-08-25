-- The one-row statement. The proof is the last two columns: the gap between
-- the books equals the unmatched ledger sum minus the unmatched bank sum, so
-- unexplained lands on 0.00 when the reconciliation accounts for everything.
WITH l AS (
    SELECT entry_id, entry_date, cents,
           ROW_NUMBER() OVER (PARTITION BY entry_date, cents ORDER BY entry_id) AS seq
    FROM ledger
),
b AS (
    SELECT txn_id, txn_date, cents,
           ROW_NUMBER() OVER (PARTITION BY txn_date, cents ORDER BY txn_id) AS seq
    FROM bank
),
exact AS (
    SELECT l.entry_id, b.txn_id
    FROM l
    JOIN b ON b.txn_date = l.entry_date AND b.cents = l.cents AND b.seq = l.seq
),
lu AS (
    SELECT * FROM ledger WHERE entry_id NOT IN (SELECT entry_id FROM exact)
),
bu AS (
    SELECT * FROM bank WHERE txn_id NOT IN (SELECT txn_id FROM exact)
),
candidates AS (
    SELECT lu.entry_id, bu.txn_id,
           ABS(julianday(bu.txn_date) - julianday(lu.entry_date)) AS days_apart
    FROM lu
    JOIN bu ON bu.cents = lu.cents
    WHERE ABS(julianday(bu.txn_date) - julianday(lu.entry_date)) <= 3
),
tolerance AS (
    SELECT entry_id, txn_id
    FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY txn_id ORDER BY days_apart, entry_id) AS bank_pick
          FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY entry_id ORDER BY days_apart, txn_id) AS pick
                FROM candidates)
          WHERE pick = 1)
    WHERE bank_pick = 1
),
sums AS (
    SELECT (SELECT SUM(cents) FROM ledger) AS ledger_cents,
           (SELECT SUM(cents) FROM bank) AS bank_cents,
           (SELECT COUNT(*) FROM exact) AS exact_matches,
           (SELECT COUNT(*) FROM tolerance) AS tolerance_matches,
           (SELECT COALESCE(SUM(cents), 0) FROM lu
             WHERE entry_id NOT IN (SELECT entry_id FROM tolerance)) AS unmatched_ledger_cents,
           (SELECT COALESCE(SUM(cents), 0) FROM bu
             WHERE txn_id NOT IN (SELECT txn_id FROM tolerance)) AS unmatched_bank_cents
)
SELECT printf('%.2f', ledger_cents / 100.0) AS ledger_total,
       printf('%.2f', bank_cents / 100.0) AS bank_total,
       printf('%.2f', (ledger_cents - bank_cents) / 100.0) AS difference,
       exact_matches,
       tolerance_matches,
       printf('%.2f', unmatched_ledger_cents / 100.0) AS unmatched_ledger,
       printf('%.2f', unmatched_bank_cents / 100.0) AS unmatched_bank,
       printf('%.2f', (unmatched_ledger_cents - unmatched_bank_cents) / 100.0) AS explained,
       printf('%.2f', ((ledger_cents - bank_cents) - (unmatched_ledger_cents - unmatched_bank_cents)) / 100.0) AS unexplained
FROM sums;

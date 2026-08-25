-- Everything neither pass could pair, from both books, in one list. Two
-- anti-joins glued with UNION ALL: the portable stand-in for a FULL OUTER
-- JOIN filtered to its null sides, which SQLite itself only gained in 3.39.
-- These rows ARE the reconciling items: outstanding cheques and deposits in
-- transit on the ledger side, fees and interest on the bank side.
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
)
SELECT 'ledger' AS side,
       entry_id AS id,
       entry_date AS day,
       description,
       printf('%.2f', cents / 100.0) AS amount
FROM lu
WHERE entry_id NOT IN (SELECT entry_id FROM tolerance)
UNION ALL
SELECT 'bank',
       txn_id,
       txn_date,
       description,
       printf('%.2f', cents / 100.0)
FROM bu
WHERE txn_id NOT IN (SELECT txn_id FROM tolerance)
ORDER BY side DESC, day;

-- Second pass over what the exact pass left behind: same amount to the cent,
-- date within three days either way, which is how a cheque written one day
-- and cleared days later still finds its bank row. Each ledger row takes its
-- nearest candidate by date, earliest bank id breaking ties, and a second
-- ranking keeps each bank row to one ledger row as well: a contested bank
-- line goes to the closest claimant and the loser stays unmatched.
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
    SELECT lu.entry_id,
           bu.txn_id,
           lu.entry_date,
           bu.txn_date,
           CAST(ABS(julianday(bu.txn_date) - julianday(lu.entry_date)) AS INTEGER) AS days_apart,
           lu.cents,
           lu.description AS ledger_description,
           bu.description AS bank_description
    FROM lu
    JOIN bu ON bu.cents = lu.cents
    WHERE ABS(julianday(bu.txn_date) - julianday(lu.entry_date)) <= 3
),
nearest AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY entry_id ORDER BY days_apart, txn_id) AS pick
    FROM candidates
),
one_per_bank_row AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY txn_id ORDER BY days_apart, entry_id) AS bank_pick
    FROM nearest
    WHERE pick = 1
)
SELECT entry_id,
       txn_id,
       entry_date,
       txn_date,
       days_apart,
       printf('%.2f', cents / 100.0) AS amount,
       ledger_description,
       bank_description
FROM one_per_bank_row
WHERE bank_pick = 1
ORDER BY entry_date;

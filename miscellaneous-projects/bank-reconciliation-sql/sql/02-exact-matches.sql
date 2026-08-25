-- One-to-one exact matches on date and amount. ROW_NUMBER gives every row a
-- sequence inside its (date, amount) group on each side, and joining on that
-- sequence pairs duplicates one-to-one instead of exploding the join: two
-- 85.00 payments on the same day pair up as two matches, not four.
WITH l AS (
    SELECT entry_id, entry_date, description, cents,
           ROW_NUMBER() OVER (PARTITION BY entry_date, cents ORDER BY entry_id) AS seq
    FROM ledger
),
b AS (
    SELECT txn_id, txn_date, description, cents,
           ROW_NUMBER() OVER (PARTITION BY txn_date, cents ORDER BY txn_id) AS seq
    FROM bank
)
SELECT l.entry_id,
       b.txn_id,
       l.entry_date AS day,
       printf('%.2f', l.cents / 100.0) AS amount,
       l.description AS ledger_description,
       b.description AS bank_description
FROM l
JOIN b ON b.txn_date = l.entry_date
      AND b.cents = l.cents
      AND b.seq = l.seq
ORDER BY l.entry_date, l.entry_id;

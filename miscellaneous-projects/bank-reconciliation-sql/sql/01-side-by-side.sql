-- Both books stacked into one shape with a source column. The totals disagree,
-- and the whole point of the queries after this one is to explain that gap
-- down to the cent. Amounts live as integer cents; printf formats them only
-- for display.
WITH stacked AS (
    SELECT 'ledger' AS book, entry_id AS id, entry_date AS day, description, cents
    FROM ledger
    UNION ALL
    SELECT 'bank', txn_id, txn_date, description, cents
    FROM bank
)
SELECT book,
       COUNT(*) AS rows_in_book,
       printf('%.2f', SUM(cents) / 100.0) AS total
FROM stacked
GROUP BY book
ORDER BY book;

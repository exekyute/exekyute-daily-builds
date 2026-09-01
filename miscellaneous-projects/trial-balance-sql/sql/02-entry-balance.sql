-- Double entry's first law, checked per entry: the debits of every journal
-- entry equal its credits, whatever the line count. The month-end compound
-- entry posts three lines, two debits against one credit, and balances just
-- the same. On a clean journal every difference reads 0.00.
SELECT entry_id,
       MIN(entry_date) AS entry_date,
       MIN(NULLIF(memo, '')) AS memo,
       COUNT(*) AS lines,
       printf('%.2f', SUM(COALESCE(debit_cents, 0)) / 100.0) AS debits,
       printf('%.2f', SUM(COALESCE(credit_cents, 0)) / 100.0) AS credits,
       printf('%.2f', (SUM(COALESCE(debit_cents, 0)) - SUM(COALESCE(credit_cents, 0))) / 100.0) AS difference,
       CASE WHEN SUM(COALESCE(debit_cents, 0)) = SUM(COALESCE(credit_cents, 0))
            THEN 'balanced' ELSE 'OUT OF BALANCE' END AS status
FROM journal
GROUP BY entry_id
ORDER BY entry_id;

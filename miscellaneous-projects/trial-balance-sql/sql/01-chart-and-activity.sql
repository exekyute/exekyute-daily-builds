-- The chart of accounts with each account's normal side derived from its
-- type: assets and expenses grow on the debit side, liabilities, equity, and
-- revenue on the credit side. The activity columns show gross postings, not
-- balances; netting comes later.
SELECT a.account_code,
       a.name,
       a.type,
       CASE WHEN a.type IN ('asset', 'expense') THEN 'debit' ELSE 'credit' END AS normal_side,
       COUNT(j.entry_id) AS lines,
       printf('%.2f', COALESCE(SUM(j.debit_cents), 0) / 100.0) AS total_debits,
       printf('%.2f', COALESCE(SUM(j.credit_cents), 0) / 100.0) AS total_credits
FROM accounts a
LEFT JOIN journal j ON j.account_code = a.account_code
GROUP BY a.account_code, a.name, a.type
ORDER BY a.account_code;

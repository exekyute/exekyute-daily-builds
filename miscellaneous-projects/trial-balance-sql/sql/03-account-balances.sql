-- Each account netted to a single balance and shown on the side it lands on.
-- The convention: balance is debits minus credits, a positive result sits in
-- the debit column, a negative one flips sign into the credit column. An
-- account landing against its normal side would be a contra balance worth a
-- second look; this month produces none.
WITH netted AS (
    SELECT a.account_code,
           a.name,
           a.type,
           CASE WHEN a.type IN ('asset', 'expense') THEN 'debit' ELSE 'credit' END AS normal_side,
           COALESCE(SUM(j.debit_cents), 0) - COALESCE(SUM(j.credit_cents), 0) AS balance_cents
    FROM accounts a
    LEFT JOIN journal j ON j.account_code = a.account_code
    GROUP BY a.account_code, a.name, a.type
)
SELECT account_code,
       name,
       normal_side,
       CASE WHEN balance_cents > 0 THEN printf('%.2f', balance_cents / 100.0) ELSE '' END AS debit_balance,
       CASE WHEN balance_cents < 0 THEN printf('%.2f', -balance_cents / 100.0) ELSE '' END AS credit_balance,
       CASE WHEN balance_cents = 0 THEN 'no balance'
            WHEN (balance_cents > 0) = (normal_side = 'debit') THEN ''
            ELSE 'CONTRA BALANCE' END AS note
FROM netted
ORDER BY account_code;

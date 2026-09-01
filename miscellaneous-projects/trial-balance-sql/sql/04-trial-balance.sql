-- The trial balance: every account on its landing side, then a totals row
-- that is the whole point of the exercise. Because each entry balanced and
-- each posting hit exactly one account, the two columns must agree to the
-- cent, and any daylight between them means something upstream is broken.
WITH netted AS (
    SELECT a.account_code,
           a.name,
           COALESCE(SUM(j.debit_cents), 0) - COALESCE(SUM(j.credit_cents), 0) AS balance_cents
    FROM accounts a
    LEFT JOIN journal j ON j.account_code = a.account_code
    GROUP BY a.account_code, a.name
)
SELECT COALESCE(CAST(account_code AS TEXT), '') AS account,
       name,
       debit_balance,
       credit_balance,
       status
FROM (
    SELECT 0 AS is_total,
           account_code,
           name,
           CASE WHEN balance_cents > 0 THEN printf('%.2f', balance_cents / 100.0) ELSE '' END AS debit_balance,
           CASE WHEN balance_cents < 0 THEN printf('%.2f', -balance_cents / 100.0) ELSE '' END AS credit_balance,
           '' AS status
    FROM netted
    UNION ALL
    SELECT 1,
           NULL,
           'TOTAL',
           printf('%.2f', SUM(CASE WHEN balance_cents > 0 THEN balance_cents ELSE 0 END) / 100.0),
           printf('%.2f', SUM(CASE WHEN balance_cents < 0 THEN -balance_cents ELSE 0 END) / 100.0),
           CASE WHEN SUM(balance_cents) = 0 THEN 'in balance' ELSE 'OUT OF BALANCE' END
    FROM netted
)
-- The numeric flag pins the totals row last no matter what any account is
-- named, and ordering on the integer code keeps mixed-width codes in the
-- same order the other reports use.
ORDER BY is_total, account_code;

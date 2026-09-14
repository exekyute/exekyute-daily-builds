-- The schedule, with the balance carried from month to month by a
-- recursive CTE. Each step reads the row the step before it produced: it
-- adds a month's interest to the balance, rounded to the cent, and takes
-- off the payment. MAX(..., 0) ends a loan early if a payment would clear
-- it, and the last month of a loan's term is set to 0 outright, which
-- makes the final payment whatever is left. The stated payment is
-- rounded to the cent and so is every month's interest, so equal
-- payments need not land on exactly zero; the final payment takes up the
-- difference. The recursion stops once a balance reaches 0 or the term
-- is up.
--
-- The recursion carries only the balance. Each month's interest, payment,
-- and principal are worked out afterward from the balance before and
-- after it.
WITH RECURSIVE balances(loan_id, month, balance) AS (
    SELECT loan_id, 0, principal FROM loans
    UNION ALL
    SELECT b.loan_id,
           b.month + 1,
           CASE WHEN b.month + 1 = l.months THEN 0
                ELSE MAX(b.balance + (b.balance * l.rate_bp + 60000) / 120000 - l.payment, 0) END
    FROM balances b
    JOIN loans l ON l.loan_id = b.loan_id
    WHERE b.balance > 0 AND b.month < l.months
),
priced AS (
    SELECT b.loan_id,
           b.month,
           b.balance,
           p.balance AS opening,
           (p.balance * l.rate_bp + 60000) / 120000 AS interest
    FROM balances b
    JOIN balances p ON p.loan_id = b.loan_id AND p.month = b.month - 1
    JOIN loans l ON l.loan_id = b.loan_id
)
SELECT loan_id,
       month,
       printf('%.2f', (opening + interest - balance) / 100.0) AS payment,
       printf('%.2f', interest / 100.0) AS interest,
       printf('%.2f', (opening - balance) / 100.0) AS principal,
       printf('%.2f', balance / 100.0) AS balance
FROM priced
ORDER BY loan_id, month;

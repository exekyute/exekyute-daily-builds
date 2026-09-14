-- The attempt with window functions. Each month's interest depends on the
-- balance after the month before, and that balance depends on the
-- interest charged before it: the balance is a result that has to feed
-- back in as an input. A window function works over the rows a query
-- starts with and cannot read its own results, so it has no way to charge
-- interest on the true balance. This attempt charges it on the starting
-- principal, the same interest every month, and takes a running SUM of
-- what is left of each payment after it.
--
-- The months come from a recursive counter that carries only the loan
-- and the month number. Query 03 puts the balance itself into the
-- recursion.
WITH RECURSIVE counter(loan_id, month) AS (
    SELECT loan_id, 1 FROM loans
    UNION ALL
    SELECT c.loan_id, c.month + 1
    FROM counter c
    JOIN loans l ON l.loan_id = c.loan_id
    WHERE c.month < l.months
),
attempt AS (
    SELECT c.loan_id,
           c.month,
           l.months AS term,
           (l.principal * l.rate_bp + 60000) / 120000 AS interest,
           l.principal - SUM(l.payment - (l.principal * l.rate_bp + 60000) / 120000)
               OVER (PARTITION BY c.loan_id ORDER BY c.month ROWS UNBOUNDED PRECEDING) AS balance
    FROM counter c
    JOIN loans l ON l.loan_id = c.loan_id
)
SELECT loan_id,
       COUNT(*) AS payments,
       printf('%.2f', SUM(interest) / 100.0) AS interest_charged,
       printf('%.2f', MAX(CASE WHEN month = term THEN balance END) / 100.0) AS balance_after_last_payment
FROM attempt
GROUP BY loan_id
ORDER BY loan_id;

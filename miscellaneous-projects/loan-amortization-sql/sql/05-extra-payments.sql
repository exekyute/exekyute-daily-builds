-- The schedule run twice, once as agreed and once with the planned extra
-- payments, to see what the extras save. An extra payment goes in the
-- month it is planned for, after the regular payment, and it is cut down
-- to whatever is still owed, so one larger than the balance clears the
-- loan without paying more than the loan owes. In the last month of a
-- loan's term the final payment already clears everything, so an extra
-- planned for that month has nothing to go against, and neither does one
-- planned for after the loan is paid off. extra_applied shows how much
-- of the plan was used.
--
-- The recursion carries only the balance, as in query 03. Whatever came
-- off the balance beyond the regular payment in a month was extra.
WITH RECURSIVE runs(loan_id, with_extras, month, balance) AS (
    SELECT l.loan_id, s.with_extras, 0, l.principal
    FROM loans l
    CROSS JOIN (SELECT 0 AS with_extras UNION ALL SELECT 1) s
    UNION ALL
    SELECT r.loan_id,
           r.with_extras,
           r.month + 1,
           CASE WHEN r.month + 1 = l.months THEN 0
                ELSE MAX(r.balance + (r.balance * l.rate_bp + 60000) / 120000
                         - l.payment - COALESCE(e.amount, 0), 0) END
    FROM runs r
    JOIN loans l ON l.loan_id = r.loan_id
    LEFT JOIN extra_payments e
        ON r.with_extras = 1 AND e.loan_id = r.loan_id AND e.month = r.month + 1
    WHERE r.balance > 0 AND r.month < l.months
),
priced AS (
    SELECT r.loan_id,
           r.with_extras,
           r.month,
           r.balance,
           p.balance AS opening,
           l.months AS term,
           l.payment AS stated,
           (p.balance * l.rate_bp + 60000) / 120000 AS interest
    FROM runs r
    JOIN runs p ON p.loan_id = r.loan_id AND p.with_extras = r.with_extras AND p.month = r.month - 1
    JOIN loans l ON l.loan_id = r.loan_id
),
monthly AS (
    SELECT loan_id,
           with_extras,
           interest,
           (opening + interest - balance)
               - CASE WHEN month = term THEN opening + interest
                      ELSE MIN(stated, opening + interest) END AS extra
    FROM priced
),
per_run AS (
    SELECT loan_id, with_extras, COUNT(*) AS payments, SUM(interest) AS interest, SUM(extra) AS extra
    FROM monthly
    GROUP BY loan_id, with_extras
)
SELECT a.loan_id,
       a.payments AS months_as_agreed,
       x.payments AS months_with_extras,
       printf('%.2f', a.interest / 100.0) AS interest_as_agreed,
       printf('%.2f', x.interest / 100.0) AS interest_with_extras,
       printf('%.2f', (a.interest - x.interest) / 100.0) AS interest_saved,
       printf('%.2f', (SELECT COALESCE(SUM(e.amount), 0) FROM extra_payments e
                       WHERE e.loan_id = a.loan_id) / 100.0) AS extra_planned,
       printf('%.2f', x.extra / 100.0) AS extra_applied
FROM per_run a
JOIN per_run x ON x.loan_id = a.loan_id AND x.with_extras = 1
WHERE a.with_extras = 0
ORDER BY a.loan_id;

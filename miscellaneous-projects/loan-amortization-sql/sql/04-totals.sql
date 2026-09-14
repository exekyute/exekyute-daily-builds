-- What each loan costs in the end, and how far its final payment is from
-- the stated one. final_vs_stated is the final payment minus the stated
-- payment: if it is positive, paying only the stated amount in the last
-- month would have left that much owing, and if it is negative, it would
-- have paid that much too much. Total paid is the principal plus the
-- total interest.
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
),
paid AS (
    SELECT loan_id, month, opening + interest - balance AS payment, interest
    FROM priced
),
totals AS (
    SELECT loan_id,
           COUNT(*) AS payments,
           MAX(month) AS last_month,
           SUM(interest) AS interest,
           SUM(payment) AS paid
    FROM paid
    GROUP BY loan_id
)
SELECT t.loan_id,
       t.payments,
       printf('%.2f', l.payment / 100.0) AS stated_payment,
       printf('%.2f', f.payment / 100.0) AS final_payment,
       printf('%+.2f', (f.payment - l.payment) / 100.0) AS final_vs_stated,
       printf('%.2f', t.interest / 100.0) AS total_interest,
       printf('%.2f', t.paid / 100.0) AS total_paid
FROM totals t
JOIN loans l ON l.loan_id = t.loan_id
JOIN paid f ON f.loan_id = t.loan_id AND f.month = t.last_month
ORDER BY t.loan_id;

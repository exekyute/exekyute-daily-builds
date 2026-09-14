-- Each loan at a glance, with its first month's interest and the extra
-- payments planned against it. Money is held as whole cents and the rate
-- as basis points a year, so 7.20 percent is 720. A month's interest is
-- the balance times the rate over 120,000 (twelve months of 10,000 basis
-- points), rounded to the nearest cent with halves going up: adding
-- 60,000 before the integer division does that rounding for any balance
-- that is not negative.
SELECT l.loan_id,
       l.name,
       printf('%.2f', l.principal / 100.0) AS principal,
       printf('%.2f', l.rate_bp / 100.0) AS annual_rate_pct,
       l.months,
       printf('%.2f', l.payment / 100.0) AS payment,
       printf('%.2f', ((l.principal * l.rate_bp + 60000) / 120000) / 100.0) AS first_month_interest,
       printf('%.2f', (SELECT COALESCE(SUM(e.amount), 0) FROM extra_payments e
                       WHERE e.loan_id = l.loan_id) / 100.0) AS extra_planned
FROM loans l
ORDER BY l.loan_id;

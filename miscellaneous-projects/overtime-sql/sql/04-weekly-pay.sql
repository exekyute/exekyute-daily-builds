-- Each employee's pay for each week, and a total line. Shifts are split at
-- 00:00 on Sunday as in query 03, and the week's first 48 hours are paid at
-- the wage, the rest at one and a half times it. Pay is worked out in whole
-- cents: minutes times cents an hour, divided by 60 for regular time and,
-- with the half added in as times 3 over 120, for overtime, each rounded
-- half up to the cent by adding half the divisor before dividing. Regular
-- and overtime pay are rounded apart, as two lines on a pay stub would be,
-- and the total line adds up those rounded cents. It is built in the same
-- pass as the weekly lines, by reading each week twice, once for its own
-- line and once for the total, because SQLite before 3.35 works a CTE out
-- again in each SELECT that names it, so a UNION ALL of the weekly lines
-- and a total would price every week twice.
WITH timed AS (
    SELECT
        employee,
        wage_cents,
        date(starts, '-6 days', 'weekday 0') AS week,
        CAST(strftime('%s', starts) AS INTEGER) / 60 AS start_min,
        CAST(strftime('%s', ends) AS INTEGER) / 60 AS end_min,
        CAST(strftime('%s', date(starts, '-6 days', 'weekday 0'), '+7 days') AS INTEGER) / 60 AS next_week_min
    FROM shifts
),
pieces AS (
    SELECT
        t.employee,
        t.wage_cents,
        CASE WHEN p.part = 0 THEN t.week ELSE date(t.week, '+7 days') END AS week,
        CASE WHEN p.part = 0 THEN MIN(t.end_min, t.next_week_min) - t.start_min
             ELSE t.end_min - t.next_week_min END AS minutes
    FROM timed t
    CROSS JOIN (SELECT 0 AS part UNION ALL SELECT 1) p
    WHERE p.part = 0 OR t.end_min > t.next_week_min
),
weekly AS (
    -- The loader holds each employee to one wage, so MAX picks that wage.
    SELECT employee, week, MAX(wage_cents) AS wage_cents, SUM(minutes) AS worked
    FROM pieces
    GROUP BY employee, week
),
priced AS (
    SELECT
        employee,
        week,
        wage_cents,
        MIN(worked, 2880) AS regular,
        MAX(worked - 2880, 0) AS overtime,
        (MIN(worked, 2880) * wage_cents + 30) / 60 AS regular_pay,
        (MAX(worked - 2880, 0) * wage_cents * 3 + 60) / 120 AS overtime_pay
    FROM weekly
),
kinds(is_total) AS (
    SELECT 0 UNION ALL SELECT 1
),
report AS (
    SELECT
        k.is_total,
        MAX(CASE WHEN k.is_total = 0 THEN p.employee ELSE 'total' END) AS employee,
        MAX(CASE WHEN k.is_total = 0 THEN p.week END) AS week,
        MAX(CASE WHEN k.is_total = 0 THEN p.wage_cents END) AS wage_cents,
        SUM(p.regular) AS regular,
        SUM(p.overtime) AS overtime,
        SUM(p.regular_pay) AS regular_pay,
        SUM(p.overtime_pay) AS overtime_pay
    FROM priced p
    CROSS JOIN kinds k
    GROUP BY k.is_total, CASE WHEN k.is_total = 0 THEN p.employee END, CASE WHEN k.is_total = 0 THEN p.week END
)
SELECT
    employee,
    week,
    -- printf turns a missing value into 0.00, so the total line's blank wage
    -- is caught first.
    CASE WHEN wage_cents IS NULL THEN NULL ELSE printf('%.2f', wage_cents / 100.0) END AS wage,
    printf('%d:%02d', regular / 60, regular % 60) AS regular,
    printf('%d:%02d', overtime / 60, overtime % 60) AS overtime,
    printf('%.2f', regular_pay / 100.0) AS regular_pay,
    printf('%.2f', overtime_pay / 100.0) AS overtime_pay,
    printf('%.2f', (regular_pay + overtime_pay) / 100.0) AS pay
FROM report
ORDER BY is_total, employee, week;

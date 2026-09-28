-- The three ways of counting overtime side by side, week by week, and what
-- each would pay. The overtime column is Nova Scotia's rule as queries 03 and
-- 04 count it, the next two are query 02's per-shift count and its 48-hour
-- count on the hours grouped by the week each shift starts in, and pay is
-- the week's pay under the right count. The two gap columns are what each
-- quick count would pay for the week minus that pay, priced the same way:
-- its hours less its overtime at the wage and its overtime at one and a
-- half times, each rounded half up to the cent. A plus is paid over and a
-- minus is paid short. Every shift has minutes in the week it starts in,
-- so the weeks of the right count take in every week the quick counts use;
-- a week reached only by a shift carried over from the Saturday before
-- shows the quick counts at nothing. The total line adds up each column.
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
    -- The whole shift's minutes ride along on part 0, which is always in the
    -- week the shift starts in, for the two quick counts.
    SELECT
        t.employee,
        t.wage_cents,
        CASE WHEN p.part = 0 THEN t.week ELSE date(t.week, '+7 days') END AS week,
        CASE WHEN p.part = 0 THEN MIN(t.end_min, t.next_week_min) - t.start_min
             ELSE t.end_min - t.next_week_min END AS minutes,
        CASE WHEN p.part = 0 THEN t.end_min - t.start_min ELSE 0 END AS started_here
    FROM timed t
    CROSS JOIN (SELECT 0 AS part UNION ALL SELECT 1) p
    WHERE p.part = 0 OR t.end_min > t.next_week_min
),
weekly AS (
    SELECT
        employee,
        week,
        MAX(wage_cents) AS wage_cents,
        SUM(minutes) AS worked,
        SUM(started_here) AS by_start,
        SUM(MAX(started_here - 480, 0)) AS over_8
    FROM pieces
    GROUP BY employee, week
),
counted AS (
    SELECT
        employee,
        week,
        wage_cents,
        worked,
        by_start,
        MAX(worked - 2880, 0) AS overtime,
        over_8,
        MAX(by_start - 2880, 0) AS over_48_by_start
    FROM weekly
),
priced AS (
    SELECT
        employee,
        week,
        overtime,
        over_8,
        over_48_by_start,
        ((worked - overtime) * wage_cents + 30) / 60 + (overtime * wage_cents * 3 + 60) / 120 AS pay,
        ((by_start - over_8) * wage_cents + 30) / 60 + (over_8 * wage_cents * 3 + 60) / 120 AS over_8_pay,
        ((by_start - over_48_by_start) * wage_cents + 30) / 60
            + (over_48_by_start * wage_cents * 3 + 60) / 120 AS by_start_pay
    FROM counted
),
kinds(is_total) AS (
    SELECT 0 UNION ALL SELECT 1
),
report AS (
    SELECT
        k.is_total,
        MAX(CASE WHEN k.is_total = 0 THEN p.employee ELSE 'total' END) AS employee,
        MAX(CASE WHEN k.is_total = 0 THEN p.week END) AS week,
        SUM(p.overtime) AS overtime,
        SUM(p.over_8) AS over_8,
        SUM(p.over_48_by_start) AS over_48_by_start,
        SUM(p.pay) AS pay,
        SUM(p.over_8_pay - p.pay) AS over_8_gap,
        SUM(p.by_start_pay - p.pay) AS by_start_gap
    FROM priced p
    CROSS JOIN kinds k
    GROUP BY k.is_total, CASE WHEN k.is_total = 0 THEN p.employee END, CASE WHEN k.is_total = 0 THEN p.week END
)
SELECT
    employee,
    week,
    printf('%d:%02d', overtime / 60, overtime % 60) AS overtime,
    printf('%d:%02d', over_8 / 60, over_8 % 60) AS over_8_a_shift,
    printf('%d:%02d', over_48_by_start / 60, over_48_by_start % 60) AS over_48_by_start,
    printf('%.2f', pay / 100.0) AS pay,
    CASE WHEN over_8_gap = 0 THEN '0.00' ELSE printf('%+.2f', over_8_gap / 100.0) END AS over_8_gap,
    CASE WHEN by_start_gap = 0 THEN '0.00' ELSE printf('%+.2f', by_start_gap / 100.0) END AS by_start_gap
FROM report
ORDER BY is_total, employee, week;

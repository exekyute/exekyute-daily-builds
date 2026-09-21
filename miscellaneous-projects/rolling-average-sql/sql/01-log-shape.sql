-- The log at a glance: the first and last day, how many calendar days run
-- from one to the other, counting both, how many of those have a row, and
-- how many do not. A shop that shuts on Mondays leaves one day in seven out
-- of its log, so the missing days that fall on a Monday are counted apart
-- from the rest. The longest gap is the most days in a row with no row at
-- all. julianday, cut to a whole number, gives each date a day number, so a
-- gap is a subtraction, and a recursive CTE walks the calendar from the
-- first day to the last to count the Mondays in it. The walk takes its
-- ends from MIN and MAX of the day, each asked for in a query of its own,
-- which the table's key answers without reading the rows; asked for
-- together they would scan the key. So the pass over every row is named
-- only once: SQLite before 3.35 works a CTE out again every time it is
-- named.
WITH RECURSIVE
ends AS (
    SELECT
        CAST(julianday((SELECT MIN(day) FROM daily_sales)) AS INTEGER) AS first_no,
        CAST(julianday((SELECT MAX(day) FROM daily_sales)) AS INTEGER) AS last_no
),
calendar(day_no) AS (
    SELECT first_no FROM ends
    UNION ALL
    SELECT day_no + 1 FROM calendar WHERE day_no < (SELECT last_no FROM ends)
),
mondays AS (
    SELECT SUM(strftime('%w', day_no + 0.5) = '1') AS in_calendar FROM calendar
),
stepped AS (
    SELECT
        CAST(julianday(day) AS INTEGER) AS day_no,
        strftime('%w', day) = '1' AS on_monday,
        sales_cents,
        CAST(julianday(day) AS INTEGER) - CAST(julianday(LAG(day) OVER (ORDER BY day)) AS INTEGER) - 1 AS gap_before
    FROM daily_sales
),
summary AS (
    SELECT
        MIN(day_no) AS first_no,
        MAX(day_no) AS last_no,
        COUNT(*) AS logged,
        SUM(on_monday) AS logged_mondays,
        COALESCE(MAX(gap_before), 0) AS longest_gap,
        SUM(sales_cents) AS total_cents
    FROM stepped
)
SELECT
    date(s.first_no + 0.5) AS first_day,
    date(s.last_no + 0.5) AS last_day,
    s.last_no - s.first_no + 1 AS calendar_days,
    s.logged AS days_logged,
    s.last_no - s.first_no + 1 - s.logged AS days_missing,
    m.in_calendar - s.logged_mondays AS mondays_missing,
    s.last_no - s.first_no + 1 - s.logged - (m.in_calendar - s.logged_mondays) AS other_days_missing,
    s.longest_gap,
    printf('%d.%02d', s.total_cents / 100, s.total_cents % 100) AS total_sales
FROM summary s
CROSS JOIN mondays m;

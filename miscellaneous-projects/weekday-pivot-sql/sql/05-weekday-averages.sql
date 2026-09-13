-- What the ELSE 0 mistake does once someone averages the grid. The weeks
-- come from a calendar running from the log's first week to its last, so a
-- week the cafe closed entirely still counts, and every week is crossed
-- with every weekday. A cell is kept only if its date falls between the
-- first and last day in the log: a blank in the first or last week can be
-- a day the log never covered rather than a closure, and counting it as a
-- closure would invent days off that never happened.
--
-- AVG skips the NULL cells and averages the days the cafe opened; wrapping
-- the value in COALESCE to 0 counts each closed day as a day of zero sales.
-- Each average is rounded to whole cents before formatting, since printf
-- rounds the underlying float and would send an exact half cent either
-- way. The label is output as day rather than weekday on purpose: SQLite
-- resolves a name in ORDER BY to an output column before an input one, so
-- naming the label weekday would sort the rows alphabetically.
WITH RECURSIVE days AS (
    SELECT sale_date,
           DATE(sale_date, 'weekday 0', '-6 days') AS week_of,
           (CAST(strftime('%w', sale_date) AS INTEGER) + 6) % 7 AS weekday,
           cents
    FROM sales
),
period AS (
    SELECT MIN(sale_date) AS first_day,
           MAX(sale_date) AS last_day,
           MIN(week_of) AS first_week,
           MAX(week_of) AS last_week
    FROM days
),
weeks(week_of) AS (
    SELECT first_week FROM period
    UNION ALL
    SELECT DATE(w.week_of, '+7 days')
    FROM weeks w, period p
    WHERE w.week_of < p.last_week
),
weekdays(weekday, label) AS (
    VALUES (0, 'Mon'), (1, 'Tue'), (2, 'Wed'), (3, 'Thu'), (4, 'Fri'), (5, 'Sat'), (6, 'Sun')
),
grid AS (
    SELECT d.weekday,
           d.label,
           (SELECT SUM(x.cents) FROM days x
            WHERE x.week_of = w.week_of AND x.weekday = d.weekday) AS cents
    FROM weeks w
    CROSS JOIN weekdays d
    CROSS JOIN period p
    WHERE DATE(w.week_of, '+' || d.weekday || ' days') BETWEEN p.first_day AND p.last_day
)
SELECT label AS day,
       COUNT(cents) AS days_open,
       COUNT(*) AS days_in_log,
       CASE WHEN AVG(cents) IS NULL THEN ''
            ELSE printf('%.2f', ROUND(AVG(cents)) / 100.0) END AS avg_on_days_open,
       printf('%.2f', ROUND(AVG(COALESCE(cents, 0))) / 100.0) AS avg_with_closures_as_zero
FROM grid
GROUP BY weekday, label
ORDER BY weekday;

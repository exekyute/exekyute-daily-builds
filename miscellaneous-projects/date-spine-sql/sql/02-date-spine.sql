-- One row per calendar day between the first and last sale, generated with a
-- recursive CTE. The anchor is the earliest date; each step adds one day until
-- the latest date is reached.
WITH RECURSIVE bounds AS (
    SELECT MIN(sale_date) AS first_day, MAX(sale_date) AS last_day
    FROM sales
),
calendar(day) AS (
    SELECT first_day FROM bounds
    UNION ALL
    SELECT DATE(day, '+1 day')
    FROM calendar
    WHERE day < (SELECT last_day FROM bounds)
)
SELECT day,
       CASE strftime('%w', day)
           WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon' WHEN '2' THEN 'Tue'
           WHEN '3' THEN 'Wed' WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri'
           ELSE 'Sat'
       END AS weekday
FROM calendar
ORDER BY day;

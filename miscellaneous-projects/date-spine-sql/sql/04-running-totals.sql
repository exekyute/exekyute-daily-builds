-- Month-to-date sales per store on every calendar day. Because the grid has a
-- row for closed days too, the running total holds flat across them instead
-- of skipping them.
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
),
stores AS (
    SELECT DISTINCT store FROM sales
),
daily AS (
    SELECT store, sale_date AS day, SUM(amount) AS sales
    FROM sales
    GROUP BY store, sale_date
),
grid AS (
    SELECT s.store, c.day, COALESCE(d.sales, 0) AS sales
    FROM calendar c
    CROSS JOIN stores s
    LEFT JOIN daily d ON d.store = s.store AND d.day = c.day
)
SELECT store,
       day,
       sales,
       SUM(sales) OVER (PARTITION BY store ORDER BY day) AS running_total
FROM grid
ORDER BY store, day;

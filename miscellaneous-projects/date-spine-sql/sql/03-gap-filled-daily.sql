-- Every store on every calendar day, with zero on the days that had no sales.
-- The CROSS JOIN builds the full store-by-day grid; the LEFT JOIN hangs the
-- real totals on it and COALESCE turns the misses into zeros.
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
)
SELECT s.store,
       c.day,
       COALESCE(d.sales, 0)                                   AS sales,
       CASE WHEN d.sales IS NULL THEN 'no sales' ELSE '' END  AS note
FROM calendar c
CROSS JOIN stores s
LEFT JOIN daily d ON d.store = s.store AND d.day = c.day
ORDER BY s.store, c.day;

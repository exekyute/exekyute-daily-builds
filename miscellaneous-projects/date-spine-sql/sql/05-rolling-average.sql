-- Seven-day rolling average per store, computed two ways side by side.
-- calendar_7day_avg runs over the gap-filled grid, so the window is always
-- seven calendar days. naive_7row_avg runs over the sparse daily table, so
-- its window is the last seven rows that exist, which silently reaches back
-- past any closed day. The naive column is NULL on closed days because the
-- sparse table has no row to compute it on.
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
),
on_grid AS (
    SELECT store, day, sales,
           AVG(sales) OVER (
               PARTITION BY store ORDER BY day
               ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
           ) AS calendar_7day_avg
    FROM grid
),
on_sparse AS (
    SELECT store, day,
           AVG(sales) OVER (
               PARTITION BY store ORDER BY day
               ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
           ) AS naive_7row_avg
    FROM daily
)
SELECT g.store,
       g.day,
       g.sales,
       ROUND(g.calendar_7day_avg, 2) AS calendar_7day_avg,
       ROUND(n.naive_7row_avg, 2)    AS naive_7row_avg
FROM on_grid g
LEFT JOIN on_sparse n ON n.store = g.store AND n.day = g.day
ORDER BY g.store, g.day;

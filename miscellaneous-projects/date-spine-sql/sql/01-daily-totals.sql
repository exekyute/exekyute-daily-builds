-- Daily total per store from the raw sales rows. Days with no rows are simply
-- absent here, which is the problem the later queries fix.
SELECT store,
       sale_date        AS day,
       SUM(amount)      AS sales,
       COUNT(*)         AS rows_that_day
FROM sales
GROUP BY store, sale_date
ORDER BY store, sale_date;

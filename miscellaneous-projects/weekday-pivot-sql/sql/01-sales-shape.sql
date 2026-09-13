-- The log at a glance. A day the cafe was closed has no row at all, and a
-- day it opened and sold nothing has a row holding 0.00. Those are
-- different facts, and keeping them apart is what the rest of the queries
-- are about. Weeks start on Monday: moving forward to the next Sunday and
-- back six days lands on the Monday of the same week. The week count runs
-- from the first week to the last rather than counting weeks that hold a
-- row, so a week the cafe closed entirely is still one of them.
SELECT COUNT(*) AS days_trading,
       MIN(sale_date) AS first_day,
       MAX(sale_date) AS last_day,
       CAST((julianday(MAX(DATE(sale_date, 'weekday 0', '-6 days')))
             - julianday(MIN(DATE(sale_date, 'weekday 0', '-6 days')))) / 7 AS INTEGER) + 1 AS weeks,
       SUM(cents = 0) AS days_open_selling_nothing,
       printf('%.2f', SUM(cents) / 100.0) AS total_sales
FROM sales;

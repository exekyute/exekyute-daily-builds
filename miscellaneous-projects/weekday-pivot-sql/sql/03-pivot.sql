-- The pivot done right. Adding 6 and taking the remainder by 7 turns
-- strftime's Sunday-first 0 to 6 into a Monday-first 0 to 6, so each value
-- lands under its own day. Each column is a SUM over a CASE with no ELSE:
-- for a weekday with no row that week every CASE is NULL and so is the SUM,
-- while a day that opened and sold nothing contributes a real 0 and sums to
-- 0. NULL prints as a blank, so a closed day shows empty and the zero-sales
-- day shows 0.00. The NULL has to be caught before printf, which would
-- otherwise print it as 0.00 too.
WITH days AS (
    SELECT DATE(sale_date, 'weekday 0', '-6 days') AS week_of,
           (CAST(strftime('%w', sale_date) AS INTEGER) + 6) % 7 AS weekday,
           cents
    FROM sales
),
weekly AS (
    SELECT week_of,
           SUM(CASE WHEN weekday = 0 THEN cents END) AS mon,
           SUM(CASE WHEN weekday = 1 THEN cents END) AS tue,
           SUM(CASE WHEN weekday = 2 THEN cents END) AS wed,
           SUM(CASE WHEN weekday = 3 THEN cents END) AS thu,
           SUM(CASE WHEN weekday = 4 THEN cents END) AS fri,
           SUM(CASE WHEN weekday = 5 THEN cents END) AS sat,
           SUM(CASE WHEN weekday = 6 THEN cents END) AS sun
    FROM days
    GROUP BY week_of
)
SELECT week_of,
       CASE WHEN mon IS NULL THEN '' ELSE printf('%.2f', mon / 100.0) END AS mon,
       CASE WHEN tue IS NULL THEN '' ELSE printf('%.2f', tue / 100.0) END AS tue,
       CASE WHEN wed IS NULL THEN '' ELSE printf('%.2f', wed / 100.0) END AS wed,
       CASE WHEN thu IS NULL THEN '' ELSE printf('%.2f', thu / 100.0) END AS thu,
       CASE WHEN fri IS NULL THEN '' ELSE printf('%.2f', fri / 100.0) END AS fri,
       CASE WHEN sat IS NULL THEN '' ELSE printf('%.2f', sat / 100.0) END AS sat,
       CASE WHEN sun IS NULL THEN '' ELSE printf('%.2f', sun / 100.0) END AS sun
FROM weekly
ORDER BY week_of;

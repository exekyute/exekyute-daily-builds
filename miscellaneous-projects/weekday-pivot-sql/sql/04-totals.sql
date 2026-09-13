-- The grid with its margins: a total for each week down the right, and a
-- final row totalling each weekday across all four weeks. The totals row is
-- the same pivot with no GROUP BY, stacked under the weekly rows with UNION
-- ALL, and a flag column orders it last. Both margins sum the same cents,
-- so the bottom-right cell has to equal the whole log.
WITH days AS (
    SELECT DATE(sale_date, 'weekday 0', '-6 days') AS week_of,
           (CAST(strftime('%w', sale_date) AS INTEGER) + 6) % 7 AS weekday,
           cents
    FROM sales
),
grid AS (
    SELECT week_of, 0 AS is_total,
           SUM(CASE WHEN weekday = 0 THEN cents END) AS mon,
           SUM(CASE WHEN weekday = 1 THEN cents END) AS tue,
           SUM(CASE WHEN weekday = 2 THEN cents END) AS wed,
           SUM(CASE WHEN weekday = 3 THEN cents END) AS thu,
           SUM(CASE WHEN weekday = 4 THEN cents END) AS fri,
           SUM(CASE WHEN weekday = 5 THEN cents END) AS sat,
           SUM(CASE WHEN weekday = 6 THEN cents END) AS sun,
           SUM(cents) AS total
    FROM days
    GROUP BY week_of
    UNION ALL
    SELECT 'all weeks', 1,
           SUM(CASE WHEN weekday = 0 THEN cents END),
           SUM(CASE WHEN weekday = 1 THEN cents END),
           SUM(CASE WHEN weekday = 2 THEN cents END),
           SUM(CASE WHEN weekday = 3 THEN cents END),
           SUM(CASE WHEN weekday = 4 THEN cents END),
           SUM(CASE WHEN weekday = 5 THEN cents END),
           SUM(CASE WHEN weekday = 6 THEN cents END),
           SUM(cents)
    FROM days
)
SELECT week_of,
       CASE WHEN mon IS NULL THEN '' ELSE printf('%.2f', mon / 100.0) END AS mon,
       CASE WHEN tue IS NULL THEN '' ELSE printf('%.2f', tue / 100.0) END AS tue,
       CASE WHEN wed IS NULL THEN '' ELSE printf('%.2f', wed / 100.0) END AS wed,
       CASE WHEN thu IS NULL THEN '' ELSE printf('%.2f', thu / 100.0) END AS thu,
       CASE WHEN fri IS NULL THEN '' ELSE printf('%.2f', fri / 100.0) END AS fri,
       CASE WHEN sat IS NULL THEN '' ELSE printf('%.2f', sat / 100.0) END AS sat,
       CASE WHEN sun IS NULL THEN '' ELSE printf('%.2f', sun / 100.0) END AS sun,
       printf('%.2f', total / 100.0) AS total
FROM grid
ORDER BY is_total, week_of;

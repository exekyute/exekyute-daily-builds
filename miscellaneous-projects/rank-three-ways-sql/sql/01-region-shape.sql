-- Each region at a glance, ending on the column that decides whether the
-- three ranking functions will differ at all: how many reps share an amount
-- with someone else. Ties are exact-equality events, so a region whose
-- amounts are all distinct gets identical answers from all three functions
-- and none of this build's disagreements ever appear in it.
SELECT region,
       COUNT(*) AS reps,
       printf('%.2f', SUM(sales_cents) / 100.0) AS total_sales,
       printf('%.2f', MAX(sales_cents) / 100.0) AS top_sales,
       SUM(CASE WHEN sales_cents = (SELECT MAX(x.sales_cents) FROM sales x
                                    WHERE x.region = s.region)
                THEN 1 ELSE 0 END) AS reps_at_top,
       COUNT(DISTINCT sales_cents) AS distinct_amounts,
       SUM(CASE WHEN (SELECT COUNT(*) FROM sales x
                      WHERE x.region = s.region AND x.sales_cents = s.sales_cents) > 1
                THEN 1 ELSE 0 END) AS reps_in_a_tie
FROM sales s
GROUP BY region
ORDER BY region;

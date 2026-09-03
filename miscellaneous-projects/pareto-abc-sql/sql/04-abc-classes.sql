-- The classification: a product is an A if it is needed to reach the first
-- 80 percent of revenue, a B if needed to reach 95, a C after that. The
-- test is on the share accumulated BEFORE each product, not after it: a
-- catalog whose best seller alone carries 96 percent must still call that
-- product an A, and testing its own cumulative share (96, already past both
-- boundaries) would silently class the biggest earner C. The before-share
-- is the same running SUM with its frame ended one row earlier.
WITH ranked AS (
    SELECT product,
           revenue_cents,
           ROW_NUMBER() OVER (ORDER BY revenue_cents DESC, product) AS revenue_rank,
           ROUND(100.0 * COALESCE(SUM(revenue_cents) OVER (ORDER BY revenue_cents DESC, product
                                                           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)
                 / SUM(revenue_cents) OVER (), 2) AS share_before,
           ROUND(100.0 * SUM(revenue_cents) OVER (ORDER BY revenue_cents DESC, product
                                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                 / SUM(revenue_cents) OVER (), 2) AS cumulative_pct
    FROM products
)
SELECT revenue_rank,
       product,
       ROUND(revenue_cents / 100.0, 2) AS revenue,
       share_before,
       cumulative_pct,
       CASE WHEN share_before < 80.0 THEN 'A'
            WHEN share_before < 95.0 THEN 'B'
            ELSE 'C' END AS abc_class
FROM ranked
ORDER BY revenue_rank;

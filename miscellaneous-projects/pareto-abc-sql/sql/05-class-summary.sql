-- The one-line-per-class proof. On the sample the A line reads four
-- products, 20 percent of the catalog, 80 percent of the revenue, which is
-- the Pareto sentence an ops review quotes. The CASE mirrors 04, classing
-- each product on the share accumulated before it, and the two percentage
-- columns divide by window totals taken over the class roll-up itself,
-- aggregates inside window functions, so the summary needs no second pass.
WITH ranked AS (
    SELECT revenue_cents,
           ROUND(100.0 * COALESCE(SUM(revenue_cents) OVER (ORDER BY revenue_cents DESC, product
                                                           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)
                 / SUM(revenue_cents) OVER (), 2) AS share_before
    FROM products
),
classed AS (
    SELECT revenue_cents,
           CASE WHEN share_before < 80.0 THEN 'A'
                WHEN share_before < 95.0 THEN 'B'
                ELSE 'C' END AS abc_class
    FROM ranked
)
SELECT abc_class,
       COUNT(*) AS products,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_products,
       ROUND(SUM(revenue_cents) / 100.0, 2) AS revenue,
       ROUND(100.0 * SUM(revenue_cents) / SUM(SUM(revenue_cents)) OVER (), 2) AS pct_of_revenue
FROM classed
GROUP BY abc_class
ORDER BY abc_class;

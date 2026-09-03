-- The Pareto construction laid open: a running total of revenue down the
-- ranking, divided by the grand total, both from window SUMs in one pass.
-- Ties need care twice over. Ordered by revenue alone, the default RANGE
-- frame treats tied rows as one block and the two 60.00 products would each
-- print a running total that includes the other. The name tiebreak makes
-- the ordering total, which alone prevents that merge; the explicit ROWS
-- frame states the one-row-at-a-time intent and holds even where a
-- tiebreak gets dropped.
SELECT ROW_NUMBER() OVER (ORDER BY revenue_cents DESC, product) AS revenue_rank,
       product,
       ROUND(revenue_cents / 100.0, 2) AS revenue,
       ROUND(SUM(revenue_cents) OVER (ORDER BY revenue_cents DESC, product
                                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) / 100.0, 2) AS running_revenue,
       ROUND(100.0 * SUM(revenue_cents) OVER (ORDER BY revenue_cents DESC, product
                                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(revenue_cents) OVER (), 2) AS cumulative_pct
FROM products
ORDER BY revenue_rank;

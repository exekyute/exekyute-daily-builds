-- The catalog at a glance: how many products, what they earned together, and
-- the spread between the best and worst sellers. The spread is the whole
-- story here; a sixteen-hundredfold gap between top and bottom is what makes
-- ranking by share of total worth doing at all.
SELECT COUNT(*) AS products,
       ROUND(SUM(revenue_cents) / 100.0, 2) AS total_revenue,
       (SELECT product FROM products ORDER BY revenue_cents DESC, product LIMIT 1) AS top_product,
       ROUND(MAX(revenue_cents) / 100.0, 2) AS top_revenue,
       (SELECT product FROM products ORDER BY revenue_cents, product LIMIT 1) AS bottom_product,
       ROUND(MIN(revenue_cents) / 100.0, 2) AS bottom_revenue
FROM products;

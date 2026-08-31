-- The pairs worth acting on: lift of at least 1.5 AND at least 3 orders
-- together. The count gate matters as much as the lift gate: two pairs in
-- this data lift to 1.67 on just 2 orders each, which is a coin flip wearing
-- a trend costume, and the gate keeps them off the list.
WITH n AS (
    SELECT COUNT(DISTINCT order_id) AS orders FROM order_lines
),
per_product AS (
    SELECT product, COUNT(DISTINCT order_id) AS cnt
    FROM order_lines
    GROUP BY product
),
pairs AS (
    SELECT a.product AS product_a, b.product AS product_b, COUNT(*) AS both_cnt
    FROM order_lines a
    JOIN order_lines b ON b.order_id = a.order_id
                      AND a.product < b.product
    GROUP BY a.product, b.product
)
SELECT p.product_a,
       p.product_b,
       p.both_cnt AS orders_together,
       ROUND(1.0 * p.both_cnt * n.orders / (pa.cnt * pb.cnt), 2) AS lift
FROM pairs p
JOIN per_product pa ON pa.product = p.product_a
JOIN per_product pb ON pb.product = p.product_b
CROSS JOIN n
WHERE ROUND(1.0 * p.both_cnt * n.orders / (pa.cnt * pb.cnt), 2) >= 1.5
  AND p.both_cnt >= 3
ORDER BY lift DESC, p.product_a, p.product_b;

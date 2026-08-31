-- Support and both confidences per pair. Support is the share of all orders
-- holding both products. Confidence is directional: of the orders with A, how
-- many also had B, and the two directions differ whenever the products differ
-- in popularity. Every muffin order here included a croissant, a 100 percent
-- confidence, while only 40 percent of croissant orders included a muffin.
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
       printf('%.1f%%', 100.0 * p.both_cnt / n.orders) AS support,
       printf('%.1f%%', 100.0 * p.both_cnt / pa.cnt) AS confidence_a_to_b,
       printf('%.1f%%', 100.0 * p.both_cnt / pb.cnt) AS confidence_b_to_a
FROM pairs p
JOIN per_product pa ON pa.product = p.product_a
JOIN per_product pb ON pb.product = p.product_b
CROSS JOIN n
ORDER BY p.both_cnt DESC, p.product_a, p.product_b;

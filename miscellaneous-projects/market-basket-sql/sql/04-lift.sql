-- Lift: how many times more often a pair sells together than popularity alone
-- predicts. Expected co-occurrence under independence is the product of the
-- two order counts over total orders; lift is actual over expected. The
-- espresso and croissant pair tops the raw counts at 6 and lands at exactly
-- 1.00, pure popularity, while cold brew and cookie at 5 lift to 2.78.
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
       ROUND(1.0 * pa.cnt * pb.cnt / n.orders, 1) AS expected_together,
       ROUND(1.0 * p.both_cnt * n.orders / (pa.cnt * pb.cnt), 2) AS lift,
       -- The verdict gates on the same rounded value the lift column shows,
       -- so a printed row can never contradict its own label at a boundary.
       CASE
           WHEN ROUND(1.0 * p.both_cnt * n.orders / (pa.cnt * pb.cnt), 2) >= 1.5 THEN 'above chance'
           WHEN ROUND(1.0 * p.both_cnt * n.orders / (pa.cnt * pb.cnt), 2) <= 0.67 THEN 'below chance'
           ELSE 'about chance'
       END AS verdict
FROM pairs p
JOIN per_product pa ON pa.product = p.product_a
JOIN per_product pb ON pb.product = p.product_b
CROSS JOIN n
ORDER BY lift DESC, p.product_a, p.product_b;

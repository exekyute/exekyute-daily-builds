-- Every pair of products bought in the same order, counted. The self-join on
-- order_id with product_a < product_b produces each unordered pair exactly
-- once per order: no pair twice in both directions, no product paired with
-- itself. Raw counts mislead on their own, which is the rest of the set.
SELECT a.product AS product_a,
       b.product AS product_b,
       COUNT(*) AS orders_together
FROM order_lines a
JOIN order_lines b ON b.order_id = a.order_id
                  AND a.product < b.product
GROUP BY a.product, b.product
ORDER BY orders_together DESC, product_a, product_b;

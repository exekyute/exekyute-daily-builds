-- NTILE laid open on the frequency dimension. Ten customers into five buckets
-- is two per bucket, and the bucket line does not care about ties: dev and
-- eli both placed two orders, but the boundary falls between them, so one
-- scores 1 and the other 2. The same_count_as_prev column marks every
-- customer whose count matches the row before it; in this sample each marked
-- tie also straddles a bucket line, which is exactly the hazard on show.
WITH summary AS (
    SELECT customer_id, COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id
)
SELECT customer_id,
       order_count,
       ROW_NUMBER() OVER w AS position,
       NTILE(5) OVER w AS f_score,
       CASE WHEN order_count = LAG(order_count) OVER w
            THEN 'tied with previous' ELSE '' END AS same_count_as_prev
FROM summary
WINDOW w AS (ORDER BY order_count, customer_id)
ORDER BY position;

-- Scores into words. The CASE reads top down, most specific first: strong on
-- all three dimensions is a champion; strong recency and frequency with
-- lighter spend is loyal; heavy spend gone quiet is the customer worth a
-- phone call; heavy spend still current keeps its own tier so it can never
-- fall through to regular; then the fading tiers by recency alone.
WITH summary AS (
    SELECT customer_id,
           COUNT(*) AS order_count,
           MAX(order_date) AS last_order,
           SUM(amount_cents) AS total_cents
    FROM orders
    GROUP BY customer_id
),
scored AS (
    SELECT customer_id, total_cents,
           NTILE(5) OVER (ORDER BY last_order, customer_id) AS r_score,
           NTILE(5) OVER (ORDER BY order_count, customer_id) AS f_score,
           NTILE(5) OVER (ORDER BY total_cents, customer_id) AS m_score
    FROM summary
)
SELECT customer_id,
       printf('%d%d%d', r_score, f_score, m_score) AS rfm,
       printf('%.2f', total_cents / 100.0) AS total_spend,
       CASE
           WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'champions'
           WHEN r_score >= 4 AND f_score >= 4 THEN 'loyal'
           WHEN m_score >= 4 AND r_score <= 3 THEN 'big spender at risk'
           WHEN m_score >= 4 THEN 'big spender'
           WHEN r_score = 1 THEN 'lost'
           WHEN r_score = 2 THEN 'at risk'
           ELSE 'regular'
       END AS segment
FROM scored
ORDER BY rfm DESC, customer_id;

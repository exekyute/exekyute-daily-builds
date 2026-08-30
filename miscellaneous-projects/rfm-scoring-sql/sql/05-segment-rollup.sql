-- The view a retention plan starts from: each segment's headcount, revenue,
-- share of all revenue, and how long ago its members were last seen. Three
-- champions carry roughly half the revenue; the single quiet big spender
-- carries more than the loyal and regular tiers put together.
WITH params AS (
    SELECT DATE('2026-08-30') AS as_of
),
summary AS (
    SELECT customer_id,
           COUNT(*) AS order_count,
           MAX(order_date) AS last_order,
           SUM(amount_cents) AS total_cents
    FROM orders
    GROUP BY customer_id
),
scored AS (
    SELECT customer_id, last_order, total_cents,
           NTILE(5) OVER (ORDER BY last_order, customer_id) AS r_score,
           NTILE(5) OVER (ORDER BY order_count, customer_id) AS f_score,
           NTILE(5) OVER (ORDER BY total_cents, customer_id) AS m_score
    FROM summary
),
segmented AS (
    SELECT s.*,
           CAST(julianday(p.as_of) - julianday(s.last_order) AS INTEGER) AS days_since,
           CASE
               WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'champions'
               WHEN r_score >= 4 AND f_score >= 4 THEN 'loyal'
               WHEN m_score >= 4 AND r_score <= 3 THEN 'big spender at risk'
               WHEN m_score >= 4 THEN 'big spender'
               WHEN r_score = 1 THEN 'lost'
               WHEN r_score = 2 THEN 'at risk'
               ELSE 'regular'
           END AS segment
    FROM scored s
    CROSS JOIN params p
)
SELECT segment,
       COUNT(*) AS customers,
       printf('%.2f', SUM(total_cents) / 100.0) AS revenue,
       printf('%.1f%%', 100.0 * SUM(total_cents)
                        / (SELECT SUM(total_cents) FROM segmented)) AS revenue_share,
       ROUND(AVG(days_since), 1) AS avg_days_since_order
FROM segmented
GROUP BY segment
ORDER BY SUM(total_cents) DESC;

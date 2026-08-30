-- The scores: NTILE(5) deals each customer into a quintile per dimension,
-- ordered so 5 is always best: most recent, most orders, most spend. Every
-- ORDER BY carries customer_id as a tiebreak, because NTILE has to put tied
-- customers somewhere and without the tiebreak that somewhere changes from
-- run to run.
WITH summary AS (
    SELECT customer_id,
           COUNT(*) AS order_count,
           MAX(order_date) AS last_order,
           SUM(amount_cents) AS total_cents
    FROM orders
    GROUP BY customer_id
),
scored AS (
    SELECT customer_id, order_count, last_order, total_cents,
           NTILE(5) OVER (ORDER BY last_order, customer_id) AS r_score,
           NTILE(5) OVER (ORDER BY order_count, customer_id) AS f_score,
           NTILE(5) OVER (ORDER BY total_cents, customer_id) AS m_score
    FROM summary
)
SELECT customer_id,
       last_order,
       order_count,
       printf('%.2f', total_cents / 100.0) AS total_spend,
       r_score,
       f_score,
       m_score,
       printf('%d%d%d', r_score, f_score, m_score) AS rfm
FROM scored
ORDER BY rfm DESC, customer_id;

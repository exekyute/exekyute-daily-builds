-- The raw material for scoring: one row per customer with the three facts RFM
-- is named after. Recency counts days back from a pinned report date so the
-- sample data gives the same answer every run; swap it for DATE('now')
-- against live data.
WITH params AS (
    SELECT DATE('2026-08-30') AS as_of
)
SELECT o.customer_id,
       COUNT(*) AS orders,
       MAX(o.order_date) AS last_order,
       CAST(julianday(p.as_of) - julianday(MAX(o.order_date)) AS INTEGER) AS days_since,
       printf('%.2f', SUM(o.amount_cents) / 100.0) AS total_spend
FROM orders o
CROSS JOIN params p
GROUP BY o.customer_id
ORDER BY o.customer_id;

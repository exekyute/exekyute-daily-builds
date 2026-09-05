-- The as-of join done right, in two moves: a correlated subquery picks the
-- KEY of the newest rate at or before each order date, then one LEFT JOIN
-- brings that rate's payload back. LEFT, because an order older than every
-- rate version must surface with a note instead of vanishing the way the
-- naive inner join dropped it, and its tax stays NULL rather than
-- defaulting to zero as if it were tax-free. Tax and gross both go through
-- the same rounded-cents integer, one rounding policy per row, so net plus
-- the printed tax always equals the printed gross.
WITH picked AS (
    SELECT o.order_id,
           o.order_date,
           o.customer,
           o.net_cents,
           (SELECT r.effective_date
            FROM tax_rates r
            WHERE r.effective_date <= o.order_date
            ORDER BY r.effective_date DESC
            LIMIT 1) AS rate_effective
    FROM orders o
)
SELECT p.order_id,
       p.order_date,
       p.customer,
       ROUND(p.net_cents / 100.0, 2) AS net,
       p.rate_effective,
       ROUND(r.rate_bp / 100.0, 2) AS rate_percent,
       ROUND(CAST(ROUND(p.net_cents * r.rate_bp / 10000.0) AS INTEGER) / 100.0, 2) AS tax,
       ROUND((p.net_cents + CAST(ROUND(p.net_cents * r.rate_bp / 10000.0) AS INTEGER)) / 100.0, 2) AS gross,
       CASE WHEN p.rate_effective IS NULL THEN 'no rate in force' ELSE '' END AS note
FROM picked p
LEFT JOIN tax_rates r ON r.effective_date = p.rate_effective
ORDER BY p.order_date, p.order_id;

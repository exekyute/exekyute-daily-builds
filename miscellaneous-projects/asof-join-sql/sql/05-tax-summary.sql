-- The one-line reconciliation of trap versus truth: the as-of figure and
-- the naive figure side by side with the overstatement between them, plus
-- the order the naive join lost. On the sample the naive join more than
-- doubles the tax bill, the kind of error that survives review precisely
-- because every individual joined row looks plausible on its own.
WITH asof AS (
    SELECT o.order_id,
           o.net_cents,
           (SELECT r.rate_bp
            FROM tax_rates r
            WHERE r.effective_date <= o.order_date
            ORDER BY r.effective_date DESC
            LIMIT 1) AS rate_bp
    FROM orders o
),
naive AS (
    SELECT COUNT(*) AS joined_rows,
           SUM(o.net_cents * r.rate_bp) AS tax_product
    FROM orders o
    JOIN tax_rates r ON r.effective_date <= o.order_date
)
SELECT (SELECT COUNT(*) FROM orders) AS orders,
       (SELECT COUNT(*) FROM asof WHERE rate_bp IS NOT NULL) AS orders_priced,
       (SELECT COUNT(*) FROM asof WHERE rate_bp IS NULL) AS orders_no_rate,
       (SELECT ROUND(COALESCE(SUM(net_cents), 0) / 100.0, 2) FROM asof WHERE rate_bp IS NOT NULL) AS net_priced,
       (SELECT ROUND(COALESCE(SUM(net_cents * rate_bp), 0) / 1000000.0, 2) FROM asof) AS tax_asof,
       (SELECT joined_rows FROM naive) AS naive_rows,
       (SELECT ROUND(COALESCE(tax_product, 0) / 1000000.0, 2) FROM naive) AS naive_tax,
       ROUND(COALESCE((SELECT tax_product FROM naive), 0) / 1000000.0
             - COALESCE((SELECT SUM(net_cents * rate_bp) FROM asof), 0) / 1000000.0, 2) AS overstatement;

-- The trap, laid open on purpose: joining on effective_date <= order_date
-- alone matches every PAST rate version, not the one in force. Every order
-- after the second rate change collects two or three rate rows and the tax
-- adds up across all of them, while the one order older than every rate
-- matches nothing and silently vanishes from the inner join. Fifteen
-- orders come out as twenty-nine rows claiming 1,491.00 of tax; the real
-- figure is 721.00.
SELECT o.order_id,
       o.order_date,
       COUNT(*) AS rates_matched,
       ROUND(SUM(o.net_cents * r.rate_bp) / 1000000.0, 2) AS naive_tax
FROM orders o
JOIN tax_rates r ON r.effective_date <= o.order_date
GROUP BY o.order_id, o.order_date
ORDER BY o.order_date, o.order_id;

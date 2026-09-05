-- Both tables at a glance: the orders to be priced and the rate versions
-- they must be priced against. Three rate versions are live across the
-- order span and one order predates them all, which is the whole
-- difficulty: an order's tax depends on WHEN it happened, not on any key
-- the two tables share.
SELECT (SELECT COUNT(*) FROM orders) AS orders,
       (SELECT MIN(order_date) FROM orders) AS first_order,
       (SELECT MAX(order_date) FROM orders) AS last_order,
       (SELECT ROUND(SUM(net_cents) / 100.0, 2) FROM orders) AS net_total,
       (SELECT COUNT(*) FROM tax_rates) AS rate_versions,
       (SELECT MIN(effective_date) FROM tax_rates) AS first_rate,
       (SELECT MAX(effective_date) FROM tax_rates) AS latest_rate;

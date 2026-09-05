-- The same join a second way: LEAD turns the rate list into eras, each
-- valid from its effective date until the next one starts, the last left
-- open-ended. Orders then range-join into their era. Materializing eras is
-- what a warehouse does when the per-row correlated pick gets expensive,
-- and the era totals matching 03 is the check that both constructions read
-- the calendar the same way.
WITH eras AS (
    SELECT effective_date AS valid_from,
           LEAD(effective_date) OVER (ORDER BY effective_date) AS valid_until,
           rate_bp
    FROM tax_rates
)
SELECT e.valid_from,
       COALESCE(e.valid_until, 'open') AS valid_until,
       ROUND(e.rate_bp / 100.0, 2) AS rate_percent,
       COUNT(o.order_id) AS orders,
       ROUND(COALESCE(SUM(o.net_cents), 0) / 100.0, 2) AS net,
       ROUND(COALESCE(SUM(o.net_cents * e.rate_bp), 0) / 1000000.0, 2) AS tax
FROM eras e
LEFT JOIN orders o ON o.order_date >= e.valid_from
                  AND (e.valid_until IS NULL OR o.order_date < e.valid_until)
GROUP BY e.valid_from, e.valid_until, e.rate_bp
ORDER BY e.valid_from;

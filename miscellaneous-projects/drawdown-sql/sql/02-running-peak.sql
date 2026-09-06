-- The core construction: a cumulative MAX gives each day the highest value
-- the series has ever reached, and drawdown is the percent gap between the
-- day and that peak. The comparison is on exact cents and the boundary is
-- strict: a day equal to its running peak is AT the peak, not underwater,
-- which is also what lets a later re-touch of an old peak end a drawdown.
SELECT value_date,
       ROUND(value_cents / 100.0, 2) AS value,
       ROUND(MAX(value_cents) OVER w / 100.0, 2) AS running_peak,
       ROUND(100.0 * (MAX(value_cents) OVER w - value_cents) / MAX(value_cents) OVER w, 2) AS drawdown_pct,
       CASE WHEN value_cents < MAX(value_cents) OVER w THEN 'underwater' ELSE '' END AS status
FROM portfolio
WINDOW w AS (ORDER BY value_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
ORDER BY value_date;

-- The line a statement would print for today: where the series stands
-- against its own high-water mark. The trailing underwater count is every
-- day after the last day the series sat at its peak, which is zero when
-- the latest value IS the peak, and the whole row collapses to 'at peak'
-- with no drawdown to report.
WITH scored AS (
    SELECT value_date,
           value_cents,
           MAX(value_cents) OVER (ORDER BY value_date
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak_cents
    FROM portfolio
),
latest AS (
    SELECT * FROM scored ORDER BY value_date DESC LIMIT 1
),
last_peak_day AS (
    SELECT MAX(value_date) AS at_peak_on FROM scored WHERE value_cents = peak_cents
)
SELECT l.value_date AS as_of,
       ROUND(l.value_cents / 100.0, 2) AS value,
       ROUND(l.peak_cents / 100.0, 2) AS running_peak,
       (SELECT MIN(s.value_date) FROM scored s, latest l2
        WHERE s.value_cents = l2.peak_cents) AS peak_set_on,
       CASE WHEN l.value_cents < l.peak_cents THEN 'underwater' ELSE 'at peak' END AS status,
       (SELECT COUNT(*) FROM scored s, last_peak_day d WHERE s.value_date > d.at_peak_on) AS days_underwater,
       ROUND(100.0 * (l.peak_cents - l.value_cents) / l.peak_cents, 2) AS drawdown_pct
FROM latest l;

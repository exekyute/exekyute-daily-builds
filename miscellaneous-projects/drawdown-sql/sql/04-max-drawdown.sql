-- The headline number: the single worst day-versus-peak gap in the series,
-- with its full anatomy. A tie at the worst depth breaks to the earliest
-- day on purpose, so the answer is deterministic. The peak date is the day
-- that peak value was FIRST reached, and the recovery is the first later
-- day back at or above it, so the row reads as a complete story: how high,
-- how far down, how long down, how long back. A series that never dipped
-- has a worst depth of zero, and the recovery fields say so instead of
-- passing off the next ordinary day as a recovery event.
WITH scored AS (
    SELECT value_date,
           value_cents,
           MAX(value_cents) OVER (ORDER BY value_date
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak_cents
    FROM portfolio
),
worst AS (
    SELECT value_date AS trough_date, value_cents AS trough_cents, peak_cents
    FROM scored
    ORDER BY 100.0 * (peak_cents - value_cents) / peak_cents DESC, value_date
    LIMIT 1
),
peakday AS (
    SELECT (SELECT MIN(s.value_date) FROM scored s, worst w
            WHERE s.value_cents = w.peak_cents AND s.value_date <= w.trough_date) AS peak_date
),
recovery AS (
    SELECT (SELECT MIN(s.value_date) FROM scored s, worst w
            WHERE s.value_date > w.trough_date AND s.value_cents >= w.peak_cents) AS rec_date
)
SELECT ROUND(w.peak_cents / 100.0, 2) AS peak_value,
       p.peak_date AS peak_first_reached,
       w.trough_date,
       ROUND(w.trough_cents / 100.0, 2) AS trough_value,
       ROUND(100.0 * (w.peak_cents - w.trough_cents) / w.peak_cents, 2) AS max_drawdown_pct,
       CAST(julianday(w.trough_date) - julianday(p.peak_date) AS INTEGER) AS days_peak_to_trough,
       CASE WHEN w.peak_cents = w.trough_cents THEN 'never underwater'
            ELSE COALESCE(r.rec_date, 'not yet') END AS recovered_on,
       CASE WHEN w.peak_cents = w.trough_cents THEN NULL
            ELSE CAST(julianday(r.rec_date) - julianday(w.trough_date) AS INTEGER) END AS days_to_recover
FROM worst w, peakday p, recovery r;

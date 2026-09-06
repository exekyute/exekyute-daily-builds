-- Every underwater stretch as one row, by the flag-then-running-sum island
-- trick. One fact makes the per-stretch math easy: while the series is
-- underwater the running peak cannot move, so within a stretch the peak is
-- a constant and the trough is simply the minimum value. A stretch that
-- ends before the data does was ended by a recovery, so recovered_on is
-- just the next calendar day; a stretch still open at the last row has not
-- recovered yet.
WITH scored AS (
    SELECT value_date,
           value_cents,
           MAX(value_cents) OVER (ORDER BY value_date
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak_cents
    FROM portfolio
),
flagged AS (
    SELECT value_date, value_cents, peak_cents,
           CASE WHEN value_cents < peak_cents THEN 1 ELSE 0 END AS underwater
    FROM scored
),
starts AS (
    SELECT value_date, value_cents, peak_cents, underwater,
           CASE WHEN underwater = 1
                     AND COALESCE(LAG(underwater) OVER (ORDER BY value_date), 0) = 0
                THEN 1 ELSE 0 END AS opens_stretch
    FROM flagged
),
numbered AS (
    SELECT value_date, value_cents, peak_cents, underwater,
           SUM(opens_stretch) OVER (ORDER BY value_date
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS stretch
    FROM starts
),
stretches AS (
    SELECT stretch,
           MIN(value_date) AS start_date,
           MAX(value_date) AS last_day,
           MAX(peak_cents) AS peak_cents,
           MIN(value_cents) AS trough_cents,
           COUNT(*) AS days_underwater
    FROM numbered
    WHERE underwater = 1
    GROUP BY stretch
)
SELECT s.start_date,
       ROUND(s.peak_cents / 100.0, 2) AS peak_value,
       (SELECT MIN(n.value_date) FROM numbered n
        WHERE n.stretch = s.stretch AND n.underwater = 1
          AND n.value_cents = s.trough_cents) AS trough_date,
       ROUND(s.trough_cents / 100.0, 2) AS trough_value,
       ROUND(100.0 * (s.peak_cents - s.trough_cents) / s.peak_cents, 2) AS depth_pct,
       s.days_underwater,
       CASE WHEN s.last_day < (SELECT MAX(value_date) FROM portfolio)
            THEN DATE(s.last_day, '+1 day')
            ELSE 'not yet' END AS recovered_on
FROM stretches s
ORDER BY s.start_date;

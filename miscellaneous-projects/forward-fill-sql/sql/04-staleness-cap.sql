-- How much of each log a reader can actually vouch for. A carried value
-- stays a measurement only for so long; past that it is a guess with a
-- number on it. Here the cap is two hours, measured on the clock rather
-- than in rows, so a log with uneven spacing is judged by how old the
-- carried reading is and not by how many rows sit between. Every row lands
-- in exactly one of four classes, and the four always add up to the log.
WITH grouped AS (
    SELECT sensor_id,
           reading_at,
           tenths,
           COUNT(tenths) OVER (PARTITION BY sensor_id ORDER BY reading_at
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS readings_so_far
    FROM readings
),
filled AS (
    SELECT sensor_id,
           reading_at,
           tenths,
           MAX(CASE WHEN tenths IS NOT NULL THEN reading_at END)
               OVER (PARTITION BY sensor_id, readings_so_far) AS source_at
    FROM grouped
),
classed AS (
    SELECT sensor_id,
           CASE WHEN tenths IS NOT NULL THEN 'measured'
                WHEN source_at IS NULL THEN 'before first reading'
                WHEN (CAST(strftime('%s', reading_at) AS INTEGER)
                      - CAST(strftime('%s', source_at) AS INTEGER)) / 60 <= 120 THEN 'filled'
                ELSE 'too stale' END AS class
    FROM filled
)
SELECT sensor_id,
       SUM(class = 'measured') AS measured,
       SUM(class = 'filled') AS filled,
       SUM(class = 'too stale') AS too_stale,
       SUM(class = 'before first reading') AS before_first_reading,
       COUNT(*) AS log_rows
FROM classed
GROUP BY sensor_id
ORDER BY sensor_id;

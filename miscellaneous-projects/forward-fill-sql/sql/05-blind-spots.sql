-- The stretches nobody can vouch for, and what happened next. Two kinds
-- qualify. A too-stale window is the part of a run after its carried
-- reading passes the cap. A dark start is the run before a sensor's first
-- reading, and it is the more blind of the two, since a log that begins
-- while a sensor is already offline carries no value at all into it.
--
-- Either kind sits inside a single readings_so_far group, so grouping on
-- it turns each window into one line, with group zero always being the
-- dark start.
-- The first real reading after a window is the only evidence about what
-- the sensor saw while it was dark. When that reading is over the limit
-- the sensor was in breach by the time it reported, and nothing in the
-- window says when during the dark stretch the breach began.
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
           readings_so_far,
           MAX(tenths) OVER (PARTITION BY sensor_id, readings_so_far) AS fill_tenths,
           MAX(CASE WHEN tenths IS NOT NULL THEN reading_at END)
               OVER (PARTITION BY sensor_id, readings_so_far) AS source_at
    FROM grouped
),
windows AS (
    SELECT sensor_id,
           readings_so_far,
           MIN(reading_at) AS from_at,
           MAX(reading_at) AS to_at,
           COUNT(*) AS rows_unvouched,
           MAX(fill_tenths) AS claimed_tenths
    FROM filled
    WHERE tenths IS NULL
      AND (source_at IS NULL
           OR (CAST(strftime('%s', reading_at) AS INTEGER)
               - CAST(strftime('%s', source_at) AS INTEGER)) / 60 > 120)
    GROUP BY sensor_id, readings_so_far
),
next_reading AS (
    SELECT w.*,
           (SELECT r.reading_at FROM readings r
            WHERE r.sensor_id = w.sensor_id AND r.reading_at > w.to_at AND r.tenths IS NOT NULL
            ORDER BY r.reading_at LIMIT 1) AS next_at,
           (SELECT r.tenths FROM readings r
            WHERE r.sensor_id = w.sensor_id AND r.reading_at > w.to_at AND r.tenths IS NOT NULL
            ORDER BY r.reading_at LIMIT 1) AS next_tenths
    FROM windows w
)
SELECT n.sensor_id,
       s.location,
       CASE WHEN n.readings_so_far = 0 THEN 'dark start' ELSE 'too stale' END AS kind,
       n.from_at,
       n.to_at,
       n.rows_unvouched,
       CASE WHEN n.claimed_tenths IS NULL THEN ''
            ELSE printf('%.1f', n.claimed_tenths / 10.0) END AS fill_would_claim,
       COALESCE(n.next_at, '') AS next_reading_at,
       CASE WHEN n.next_tenths IS NULL THEN ''
            ELSE printf('%.1f', n.next_tenths / 10.0) END AS next_reading,
       printf('%.1f', s.max_tenths / 10.0) AS limit_celsius,
       CASE WHEN n.next_tenths IS NULL THEN 'no reading since'
            WHEN n.next_tenths > s.max_tenths THEN 'breach'
            ELSE 'within limit' END AS verdict
FROM next_reading n
JOIN sensors s ON s.sensor_id = n.sensor_id
ORDER BY n.sensor_id, n.from_at;

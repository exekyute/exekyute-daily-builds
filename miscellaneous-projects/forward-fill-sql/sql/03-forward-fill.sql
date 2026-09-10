-- Forward fill in one pass. SQLite has no LAG ... IGNORE NULLS, so the
-- construction borrows a property of COUNT instead: a running COUNT of the
-- reading column skips the empty rows, so it only advances when a real
-- reading arrives. Every missing row therefore shares its readings_so_far
-- value with the last real reading before it, and that value works as a
-- group key.
-- Every group except group zero holds exactly one real reading, the one
-- that advanced the counter, so MAX over the group returns it. Rows before
-- a sensor's first reading sit in group zero, which holds no reading at
-- all, and correctly get nothing.
-- The same group also yields when that reading was taken, but only through
-- a mask. Every row carries a timestamp, so a bare MAX would return the
-- latest row in the group; CASE WHEN tenths IS NOT NULL keeps just the
-- reading's own, which is what the staleness column needs.
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
)
SELECT sensor_id,
       reading_at,
       CASE WHEN tenths IS NULL THEN ''
            ELSE printf('%.1f', tenths / 10.0) END AS measured,
       readings_so_far,
       CASE WHEN fill_tenths IS NULL THEN ''
            ELSE printf('%.1f', fill_tenths / 10.0) END AS filled,
       COALESCE(source_at, '') AS from_reading_at,
       CASE WHEN source_at IS NULL THEN NULL
            ELSE (CAST(strftime('%s', reading_at) AS INTEGER)
                  - CAST(strftime('%s', source_at) AS INTEGER)) / 60 END AS minutes_old
FROM filled
ORDER BY sensor_id, reading_at;

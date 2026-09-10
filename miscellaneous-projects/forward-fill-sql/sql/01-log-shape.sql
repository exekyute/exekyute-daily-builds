-- Each sensor at a glance. COUNT of a column skips NULLs, so COUNT of the
-- timestamp counts logged rows and COUNT of the reading counts only the
-- rows that carry one; query 03 turns that same behaviour into a running
-- counter. COUNT(*) would not do for the first: under the LEFT JOIN it
-- counts one phantom row for a sensor listed with no readings at all.
SELECT s.sensor_id,
       s.location,
       printf('%.1f', s.max_tenths / 10.0) AS limit_celsius,
       COUNT(r.reading_at) AS log_rows,
       COUNT(r.tenths) AS measured,
       COUNT(r.reading_at) - COUNT(r.tenths) AS missing,
       MIN(r.reading_at) AS first_row,
       MAX(r.reading_at) AS last_row
FROM sensors s
LEFT JOIN readings r ON r.sensor_id = s.sensor_id
GROUP BY s.sensor_id, s.location, s.max_tenths
ORDER BY s.sensor_id;

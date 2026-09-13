-- How many calls were live on average, two ways, over the span from the
-- first call to the last hang-up. Both use the timeline rows that have a
-- length: the closing row, back at 0 with no to_time, is left out.
-- Averaging the live column over those rows weights every row the same,
-- so a stretch of a few minutes counts as much as the lunch lull, and a
-- busy hour with a change every few minutes adds many rows. Weighting
-- each row by its minutes gives the average over the clock.
--
-- Live times minutes, summed over the timeline, adds up every call's
-- minutes, so the time-weighted average also equals the call minutes
-- divided by the span; the last column works it that way as a
-- cross-check. Each average is rounded to hundredths before formatting,
-- since printf rounds the underlying float and would send an exact half
-- either way.
WITH events AS (
    SELECT started_at AS event_time, 1 AS delta FROM calls
    UNION ALL
    SELECT ended_at, -1 FROM calls
),
changes AS (
    SELECT event_time, SUM(delta) AS net
    FROM events
    GROUP BY event_time
    HAVING SUM(delta) <> 0
),
timeline AS (
    SELECT event_time AS from_time,
           LEAD(event_time) OVER (ORDER BY event_time) AS to_time,
           SUM(net) OVER (ORDER BY event_time ROWS UNBOUNDED PRECEDING) AS live
    FROM changes
),
timed AS (
    SELECT live, (strftime('%s', to_time) - strftime('%s', from_time)) / 60 AS minutes
    FROM timeline
    WHERE to_time IS NOT NULL
),
log AS (
    SELECT SUM((strftime('%s', ended_at) - strftime('%s', started_at)) / 60) AS call_minutes,
           (strftime('%s', MAX(ended_at)) - strftime('%s', MIN(started_at))) / 60 AS span_minutes
    FROM calls
)
SELECT COUNT(*) AS rows_with_length,
       printf('%.2f', ROUND(100.0 * SUM(live) / COUNT(*)) / 100.0) AS avg_over_rows,
       printf('%.2f', ROUND(100.0 * SUM(live * minutes) / SUM(minutes)) / 100.0) AS avg_over_minutes,
       (SELECT printf('%.2f', ROUND(100.0 * call_minutes / span_minutes) / 100.0)
        FROM log) AS call_minutes_over_span
FROM timed;

-- The stretches when more calls were live than the three agents on shift
-- could take, built on query 03's timeline. A running count of the rows
-- at three or fewer stays the same across a run of rows over three, so
-- it serves as the key that groups each run into one stretch. Every call
-- past the third is a caller on hold, assuming an agent picks up as soon
-- as one is free, so live minus three, times the minutes, summed over a
-- stretch, is the caller-minutes spent on hold.
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
runs AS (
    SELECT from_time,
           to_time,
           live,
           (strftime('%s', to_time) - strftime('%s', from_time)) / 60 AS minutes,
           SUM(CASE WHEN live > 3 THEN 0 ELSE 1 END)
               OVER (ORDER BY from_time ROWS UNBOUNDED PRECEDING) AS run
    FROM timeline
)
SELECT MIN(from_time) AS from_time,
       MAX(to_time) AS to_time,
       SUM(minutes) AS minutes,
       MAX(live) AS peak_live,
       SUM((live - 3) * minutes) AS caller_minutes_on_hold
FROM runs
WHERE live > 3
GROUP BY run
ORDER BY MIN(from_time);

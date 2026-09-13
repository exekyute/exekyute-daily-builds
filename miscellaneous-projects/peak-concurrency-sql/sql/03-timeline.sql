-- The live-call count done right: every minute the count changed, what it
-- changed to, and how long it held. The events are netted per minute
-- before the running SUM, so a call ending and another starting in the
-- same minute cancel out instead of counting as two calls for a step. A
-- minute whose changes net to zero drops out, since the count did not
-- change there, and each row's to_time is the next minute it did.
--
-- The last row is the final hang-up: the count is back to 0 and there is
-- no to_time after it.
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
)
SELECT from_time,
       to_time,
       live,
       (strftime('%s', to_time) - strftime('%s', from_time)) / 60 AS minutes
FROM timeline
ORDER BY from_time;

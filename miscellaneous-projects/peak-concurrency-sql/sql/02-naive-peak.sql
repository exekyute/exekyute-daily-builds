-- The obvious first sweep. Every call becomes two events, +1
-- when it starts and -1 when it ends, and a running SUM over the events in
-- time order gives the number of calls live after each one. The mistake
-- is the tiebreak: when one call ends and another starts in the same
-- minute, this query takes the start first, so for one step both calls
-- count as live. That keeps a call on the line in the minute it ended,
-- which its own length contradicts: a call from 10:00 to 10:30 lasted 30
-- minutes, 10:00 through 10:29, and its line was free at 10:30.
--
-- The rows shown are every step where the count passes the three agents
-- on shift, the moments this query says a caller was on hold.
WITH events AS (
    SELECT started_at AS event_time, 1 AS delta, call_id FROM calls
    UNION ALL
    SELECT ended_at, -1, call_id FROM calls
),
swept AS (
    SELECT ROW_NUMBER() OVER (ORDER BY event_time, delta DESC, call_id) AS step,
           event_time,
           CASE delta WHEN 1 THEN 'start' ELSE 'end' END AS event,
           call_id,
           SUM(delta) OVER (ORDER BY event_time, delta DESC, call_id
                            ROWS UNBOUNDED PRECEDING) AS live
    FROM events
)
SELECT step, event_time, event, call_id, live
FROM swept
WHERE live > 3
ORDER BY step;

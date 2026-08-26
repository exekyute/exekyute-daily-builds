-- One row per funnel entrant with the timestamp they reached each stage, in
-- order: each stage is the user's first matching event AT OR AFTER the stage
-- before it. The chain of CTEs enforces the ordering; the LEFT JOINs keep
-- drop-offs in the result with NULLs from their exit stage on. MIN also
-- absorbs repeat events, so firing project_created twice changes nothing.
WITH s1 AS (
    SELECT user_id, MIN(event_ts) AS signup_ts
    FROM events
    WHERE event_name = 'signup'
    GROUP BY user_id
),
s2 AS (
    SELECT e.user_id, MIN(e.event_ts) AS project_ts
    FROM events e
    JOIN s1 ON s1.user_id = e.user_id
    WHERE e.event_name = 'project_created' AND e.event_ts >= s1.signup_ts
    GROUP BY e.user_id
),
s3 AS (
    SELECT e.user_id, MIN(e.event_ts) AS teammate_ts
    FROM events e
    JOIN s2 ON s2.user_id = e.user_id
    WHERE e.event_name = 'teammate_invited' AND e.event_ts >= s2.project_ts
    GROUP BY e.user_id
),
s4 AS (
    SELECT e.user_id, MIN(e.event_ts) AS purchase_ts
    FROM events e
    JOIN s3 ON s3.user_id = e.user_id
    WHERE e.event_name = 'purchased' AND e.event_ts >= s3.teammate_ts
    GROUP BY e.user_id
)
SELECT s1.user_id,
       s1.signup_ts,
       s2.project_ts,
       s3.teammate_ts,
       s4.purchase_ts
FROM s1
LEFT JOIN s2 ON s2.user_id = s1.user_id
LEFT JOIN s3 ON s3.user_id = s1.user_id
LEFT JOIN s4 ON s4.user_id = s1.user_id
ORDER BY s1.user_id;

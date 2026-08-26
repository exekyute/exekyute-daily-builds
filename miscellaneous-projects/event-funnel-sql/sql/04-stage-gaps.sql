-- How long each transition takes: hours between consecutive stages for the
-- users who made them, with a median per transition. SQLite has no
-- PERCENTILE_CONT, so the median is the middle row by ROW_NUMBER, averaging
-- the two middle rows when the count is even.
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
),
gaps AS (
    SELECT 1 AS step, 'signup to project_created' AS transition, s2.user_id,
           (strftime('%s', s2.project_ts || ':00') - strftime('%s', s1.signup_ts || ':00')) / 3600.0 AS hours
    FROM s2 JOIN s1 ON s1.user_id = s2.user_id
    UNION ALL
    SELECT 2, 'project_created to teammate_invited', s3.user_id,
           (strftime('%s', s3.teammate_ts || ':00') - strftime('%s', s2.project_ts || ':00')) / 3600.0
    FROM s3 JOIN s2 ON s2.user_id = s3.user_id
    UNION ALL
    SELECT 3, 'teammate_invited to purchased', s4.user_id,
           (strftime('%s', s4.purchase_ts || ':00') - strftime('%s', s3.teammate_ts || ':00')) / 3600.0
    FROM s4 JOIN s3 ON s3.user_id = s4.user_id
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY step ORDER BY hours) AS rn,
           COUNT(*) OVER (PARTITION BY step) AS n
    FROM gaps
)
SELECT transition,
       n AS users,
       ROUND(AVG(hours), 2) AS median_hours
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY step, transition, n
ORDER BY step;

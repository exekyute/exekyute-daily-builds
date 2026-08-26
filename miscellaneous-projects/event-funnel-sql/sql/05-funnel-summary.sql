-- The funnel itself: one row per stage with the users who reached it in
-- order, the share of signups still present, and the conversion from the
-- stage before. The two percentage columns answer different questions, and
-- the drop with the worst stage-to-stage rate is where the product problem
-- lives.
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
counts(step, stage, users) AS (
    SELECT 1, 'signup', (SELECT COUNT(*) FROM s1)
    UNION ALL SELECT 2, 'project_created', (SELECT COUNT(*) FROM s2)
    UNION ALL SELECT 3, 'teammate_invited', (SELECT COUNT(*) FROM s3)
    UNION ALL SELECT 4, 'purchased', (SELECT COUNT(*) FROM s4)
)
SELECT stage,
       users,
       printf('%.1f%%', 100.0 * users / FIRST_VALUE(users) OVER (ORDER BY step)) AS of_signups,
       printf('%.1f%%', 100.0 * users / LAG(users, 1, users) OVER (ORDER BY step)) AS of_previous
FROM counts
ORDER BY step;

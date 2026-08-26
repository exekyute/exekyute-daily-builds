-- Every user's furthest stage counted two ways. The naive column asks only
-- "did this event ever fire", one conditional MAX per stage in a single pass.
-- The ordered column comes from the chained funnel. The note names each
-- disagreement: a purchase fired before the earlier stages, or a purchase
-- from a user who never entered the funnel at all.
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
naive AS (
    SELECT user_id,
           MAX(event_name = 'signup')           AS fired1,
           MAX(event_name = 'project_created')  AS fired2,
           MAX(event_name = 'teammate_invited') AS fired3,
           MAX(event_name = 'purchased')        AS fired4
    FROM events
    GROUP BY user_id
),
compared AS (
    SELECT n.user_id,
           CASE WHEN n.fired4 THEN 4 WHEN n.fired3 THEN 3
                WHEN n.fired2 THEN 2 WHEN n.fired1 THEN 1 ELSE 0 END AS naive_stage,
           CASE WHEN s4.purchase_ts IS NOT NULL THEN 4
                WHEN s3.teammate_ts IS NOT NULL THEN 3
                WHEN s2.project_ts IS NOT NULL THEN 2
                WHEN s1.signup_ts IS NOT NULL THEN 1 ELSE 0 END AS ordered_stage
    FROM naive n
    LEFT JOIN s1 ON s1.user_id = n.user_id
    LEFT JOIN s2 ON s2.user_id = n.user_id
    LEFT JOIN s3 ON s3.user_id = n.user_id
    LEFT JOIN s4 ON s4.user_id = n.user_id
),
names(stage, stage_name) AS (
    VALUES (0, 'nothing'), (1, 'signup'), (2, 'project_created'),
           (3, 'teammate_invited'), (4, 'purchased')
)
SELECT c.user_id,
       nn.stage_name AS naive_furthest,
       oo.stage_name AS ordered_furthest,
       CASE WHEN c.ordered_stage = 0 THEN 'never signed up'
            WHEN c.naive_stage > c.ordered_stage THEN 'events fired out of order'
            ELSE '' END AS note
FROM compared c
JOIN names nn ON nn.stage = c.naive_stage
JOIN names oo ON oo.stage = c.ordered_stage
ORDER BY c.user_id;

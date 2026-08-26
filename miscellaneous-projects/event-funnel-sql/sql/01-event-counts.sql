-- The raw shape of the log: how often each event fires and how many distinct
-- users fire it. Raw counts are not a funnel: purchased shows 5 users here,
-- and the ordered funnel later finds only 3 real conversions.
SELECT event_name,
       COUNT(*) AS events,
       COUNT(DISTINCT user_id) AS users
FROM events
GROUP BY event_name
ORDER BY events DESC, event_name;

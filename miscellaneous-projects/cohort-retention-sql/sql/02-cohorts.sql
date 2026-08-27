-- Each user's cohort is the week of their first activity. The join-date range
-- inside each cohort shows the boundary working: a Sunday joiner belongs to
-- the week that started the previous Monday.
WITH firsts AS (
    SELECT user_id, MIN(activity_date) AS first_date
    FROM activity
    GROUP BY user_id
)
SELECT DATE(first_date, 'weekday 0', '-6 days') AS cohort_week,
       COUNT(*) AS cohort_size,
       MIN(first_date) AS earliest_join,
       MAX(first_date) AS latest_join
FROM firsts
GROUP BY cohort_week
ORDER BY cohort_week;

-- The long shape everything else builds on: one row per user per week they
-- were active, expressed as whole weeks since their cohort week. DISTINCT is
-- what collapses two activities in the same week into one retained cell.
WITH firsts AS (
    SELECT user_id, MIN(activity_date) AS first_date
    FROM activity
    GROUP BY user_id
),
cohorts AS (
    SELECT user_id, DATE(first_date, 'weekday 0', '-6 days') AS cohort_week
    FROM firsts
)
SELECT DISTINCT
       c.user_id,
       c.cohort_week,
       CAST((julianday(DATE(a.activity_date, 'weekday 0', '-6 days'))
           - julianday(c.cohort_week)) / 7 AS INTEGER) AS week_offset
FROM activity a
JOIN cohorts c ON c.user_id = a.user_id
ORDER BY c.cohort_week, c.user_id, week_offset;

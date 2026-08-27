-- The retention grid: one row per cohort, one column per week offset, built
-- by pivoting the long form with MAX(CASE). A blank cell means that week has
-- not happened for that cohort yet; a 0.0% cell means the week happened and
-- nobody came back. Keeping those two apart is the whole reason the spine in
-- the long form exists.
WITH firsts AS (
    SELECT user_id, MIN(activity_date) AS first_date
    FROM activity
    GROUP BY user_id
),
cohorts AS (
    SELECT user_id, DATE(first_date, 'weekday 0', '-6 days') AS cohort_week
    FROM firsts
),
sizes AS (
    SELECT cohort_week, COUNT(*) AS cohort_size
    FROM cohorts
    GROUP BY cohort_week
),
user_weeks AS (
    SELECT DISTINCT c.user_id, c.cohort_week,
           CAST((julianday(DATE(a.activity_date, 'weekday 0', '-6 days'))
               - julianday(c.cohort_week)) / 7 AS INTEGER) AS week_offset
    FROM activity a
    JOIN cohorts c ON c.user_id = a.user_id
),
params AS (
    SELECT DATE(MAX(activity_date), 'weekday 0', '-6 days') AS last_week
    FROM activity
),
bounds AS (
    -- The widest offset any cohort can observe, so the spine always covers
    -- the whole data window no matter how long the log runs.
    SELECT CAST((julianday(p.last_week) - julianday(MIN(s.cohort_week))) / 7 AS INTEGER) AS max_offset
    FROM sizes s
    CROSS JOIN params p
),
spine(n) AS (
    SELECT 0
    UNION ALL
    SELECT n + 1 FROM spine WHERE n < (SELECT max_offset FROM bounds)
),
cells AS (
    SELECT s.cohort_week, s.cohort_size, sp.n AS week_offset
    FROM sizes s
    CROSS JOIN spine sp
    CROSS JOIN params p
    WHERE julianday(s.cohort_week) + sp.n * 7 <= julianday(p.last_week)
),
long_form AS (
    SELECT ce.cohort_week,
           ce.cohort_size,
           ce.week_offset,
           printf('%.1f%%', 100.0 * COUNT(u.user_id) / ce.cohort_size) AS retention
    FROM cells ce
    LEFT JOIN user_weeks u ON u.cohort_week = ce.cohort_week
                          AND u.week_offset = ce.week_offset
    GROUP BY ce.cohort_week, ce.week_offset, ce.cohort_size
)
SELECT cohort_week,
       cohort_size,
       MAX(CASE WHEN week_offset = 0 THEN retention END) AS week_0,
       MAX(CASE WHEN week_offset = 1 THEN retention END) AS week_1,
       MAX(CASE WHEN week_offset = 2 THEN retention END) AS week_2,
       MAX(CASE WHEN week_offset = 3 THEN retention END) AS week_3
FROM long_form
GROUP BY cohort_week, cohort_size
ORDER BY cohort_week;

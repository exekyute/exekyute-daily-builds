-- Activity rolled up to Monday-start weeks. DATE(d, 'weekday 0', '-6 days')
-- advances to the Sunday that ends the week, then steps back six days to its
-- Monday, so a Sunday activity lands in the week that is ending, not the one
-- about to start.
SELECT DATE(activity_date, 'weekday 0', '-6 days') AS week_start,
       COUNT(DISTINCT user_id) AS active_users,
       COUNT(*) AS activity_rows
FROM activity
GROUP BY week_start
ORDER BY week_start;

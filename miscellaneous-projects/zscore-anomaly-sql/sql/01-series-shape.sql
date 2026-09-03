-- The series at a glance: span, overall mean, and the extremes with their
-- dates. The two extreme days are exactly the ones the z-scores later flag,
-- but eyeballing extremes is not detection; the point of the build is scoring
-- each day against its own recent past instead of the whole history.
SELECT COUNT(*) AS days,
       MIN(metric_date) AS first_day,
       MAX(metric_date) AS last_day,
       ROUND(AVG(orders), 2) AS overall_mean,
       (SELECT metric_date FROM daily_metrics ORDER BY orders, metric_date LIMIT 1) AS lowest_day,
       MIN(orders) AS lowest,
       (SELECT metric_date FROM daily_metrics ORDER BY orders DESC, metric_date LIMIT 1) AS highest_day,
       MAX(orders) AS highest
FROM daily_metrics;

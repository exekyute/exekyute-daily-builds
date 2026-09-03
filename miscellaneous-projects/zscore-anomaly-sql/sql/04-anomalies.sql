-- Just the days worth waking someone for: scores beyond two sigma in either
-- direction, plus any day whose baseline had no spread at all, which is its
-- own kind of signal about the series. Everything else stays out of the
-- pager.
WITH baselined AS (
    SELECT metric_date,
           orders,
           COUNT(*) OVER w AS window_days,
           AVG(orders) OVER w AS mean_prev,
           sqrt(MAX(0.0, AVG(orders * orders) OVER w
                - AVG(orders) OVER w * AVG(orders) OVER w)) AS sigma_prev
    FROM daily_metrics
    WINDOW w AS (ORDER BY metric_date ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING)
)
SELECT metric_date,
       orders,
       ROUND((orders - mean_prev) / NULLIF(sigma_prev, 0), 2) AS z,
       CASE
           WHEN sigma_prev = 0 THEN 'flat baseline'
           WHEN orders > mean_prev THEN 'spike'
           ELSE 'drop'
       END AS kind
FROM baselined
WHERE window_days = 14
  AND (sigma_prev = 0 OR ABS((orders - mean_prev) / sigma_prev) >= 2)
ORDER BY metric_date;

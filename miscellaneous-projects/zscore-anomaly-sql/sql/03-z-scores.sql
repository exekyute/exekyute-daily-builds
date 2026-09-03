-- The score: how many of its own trailing standard deviations each day sits
-- from its trailing mean. Only days with a full 14-day window are scored,
-- and a window with zero spread gets a flat-baseline note instead of a
-- division by zero: NULLIF turns sigma 0 into NULL, and the z rides along as
-- NULL rather than exploding.
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
       ROUND(mean_prev, 2) AS baseline_mean,
       ROUND(sigma_prev, 2) AS baseline_sigma,
       ROUND((orders - mean_prev) / NULLIF(sigma_prev, 0), 2) AS z,
       CASE
           WHEN sigma_prev = 0 THEN 'flat baseline'
           WHEN ABS((orders - mean_prev) / sigma_prev) >= 2 THEN 'anomaly'
           ELSE ''
       END AS flag
FROM baselined
WHERE window_days = 14
ORDER BY metric_date;
